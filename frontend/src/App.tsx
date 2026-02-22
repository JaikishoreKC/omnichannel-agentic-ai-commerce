import { useEffect, useMemo, useRef, useState } from "react";

import {
  addToCart,
  checkout,
  connectChat,
  ensureSession,
  fetchChatHistory,
  fetchProduct,
  fetchCart,
  fetchProducts,
  login,
  type ChatResponsePayload,
  register,
  setSessionId as setStoredSessionId,
  setToken,
} from "./api";
import type { AuthUser, Cart, InteractionHistoryMessage, Product } from "./types";

const DEFAULT_CART: Cart = {
  id: "",
  userId: null,
  sessionId: "",
  items: [],
  subtotal: 0,
  tax: 0,
  shipping: 0,
  discount: 0,
  total: 0,
  itemCount: 0,
  currency: "USD",
};

function productIdFromPath(pathname: string): string | null {
  const match = pathname.match(/^\/products\/([^/]+)\/?$/);
  if (!match) {
    return null;
  }
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
}

type ChatEntry = { role: "user" | "assistant"; text: string; agent?: string; streamId?: string };

function historyToChatEntries(history: InteractionHistoryMessage[]): ChatEntry[] {
  const output: ChatEntry[] = [];
  for (const row of history) {
    const userText = row.message?.trim();
    if (userText) {
      output.push({ role: "user", text: userText });
    }
    const assistantText = String(row.response?.message ?? "").trim();
    if (assistantText) {
      output.push({
        role: "assistant",
        text: assistantText,
        agent: row.response?.agent ?? row.agent ?? "assistant",
      });
    }
  }
  return output;
}

export default function App(): JSX.Element {
  const [products, setProducts] = useState<Product[]>([]);
  const [cart, setCart] = useState<Cart>(DEFAULT_CART);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [message, setMessage] = useState("Guest mode: browse and build your cart.");
  const [busy, setBusy] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatEntry[]>([]);
  const [chatActions, setChatActions] = useState<Array<{ label: string; action: string }>>([]);
  const [chatReady, setChatReady] = useState(false);
  const [assistantTyping, setAssistantTyping] = useState(false);
  const [path, setPath] = useState(() => window.location.pathname);
  const [detailProduct, setDetailProduct] = useState<Product | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailVariantId, setDetailVariantId] = useState("");
  const [detailQuantity, setDetailQuantity] = useState(1);
  const socketRef = useRef<WebSocket | null>(null);
  const connectSocketRef = useRef<(session: string) => void>(() => undefined);
  const reconnectTimerRef = useRef<number | null>(null);
  const intentionalSocketCloseRef = useRef(false);

  const totalItems = useMemo(() => cart.itemCount, [cart.itemCount]);
  const selectedProductId = useMemo(() => productIdFromPath(path), [path]);
  const selectedDetailVariant = useMemo(
    () => detailProduct?.variants.find((variant) => variant.id === detailVariantId) ?? null,
    [detailProduct, detailVariantId],
  );

  async function reloadData(): Promise<void> {
    const [productList, cartData] = await Promise.all([fetchProducts(), fetchCart()]);
    setProducts(productList);
    setCart(cartData);
  }

  async function reloadChatHistory(targetSessionId: string): Promise<void> {
    try {
      const payload = await fetchChatHistory({ sessionId: targetSessionId, limit: 80 });
      if (payload.sessionId && payload.sessionId !== targetSessionId) {
        setStoredSessionId(payload.sessionId);
        setSessionId(payload.sessionId);
      }
      setChatMessages(historyToChatEntries(payload.messages ?? []));
    } catch {
      // Keep existing chat state when history endpoint is unavailable.
    }
  }

  function navigateTo(pathname: string): void {
    if (window.location.pathname === pathname) {
      return;
    }
    window.history.pushState({}, "", pathname);
    setPath(pathname);
  }

  function handleChatResponse(payload: ChatResponsePayload, streamId?: string): void {
    setAssistantTyping(false);
    setChatMessages((previous) => {
      if (!streamId) {
        return [...previous, { role: "assistant", text: payload.message, agent: payload.agent }];
      }
      const hasExisting = previous.some(
        (entry) => entry.role === "assistant" && entry.streamId === streamId,
      );
      if (!hasExisting) {
        return [
          ...previous,
          {
            role: "assistant",
            text: payload.message,
            agent: payload.agent,
            streamId,
          },
        ];
      }
      return previous.map((entry) =>
        entry.role === "assistant" && entry.streamId === streamId
          ? { ...entry, text: payload.message, agent: payload.agent }
          : entry,
      );
    });
    setChatActions(payload.suggestedActions ?? []);

    const cartPayload = payload.data?.cart as Cart | undefined;
    if (cartPayload) {
      setCart(cartPayload);
    }
    const multiCart = (payload.data?.cart as { cart?: Cart } | undefined)?.cart;
    if (multiCart) {
      setCart(multiCart);
    }
    const productsPayload = payload.data?.products as Product[] | undefined;
    if (productsPayload && productsPayload.length > 0) {
      setProducts(productsPayload);
    }
  }

  function handleStreamStart(payload: { streamId: string; agent?: string }): void {
    setChatMessages((previous) => {
      const exists = previous.some(
        (entry) => entry.role === "assistant" && entry.streamId === payload.streamId,
      );
      if (exists) {
        return previous;
      }
      return [...previous, { role: "assistant", text: "", agent: payload.agent, streamId: payload.streamId }];
    });
  }

  function handleStreamDelta(payload: { streamId: string; delta: string }): void {
    setChatMessages((previous) =>
      previous.map((entry) =>
        entry.role === "assistant" && entry.streamId === payload.streamId
          ? { ...entry, text: `${entry.text}${payload.delta}` }
          : entry,
      ),
    );
  }

  function handleStreamEnd(payload: { streamId: string }): void {
    setChatMessages((previous) =>
      previous.map((entry) =>
        entry.role === "assistant" && entry.streamId === payload.streamId
          ? { ...entry, text: entry.text.trimEnd() }
          : entry,
      ),
    );
  }

  useEffect(() => {
    let active = true;
    let currentSessionId = "";

    const connectSocket = (nextSessionId: string) => {
      if (!active) {
        return;
      }
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (socketRef.current) {
        intentionalSocketCloseRef.current = true;
        socketRef.current.close();
      }
      setChatReady(false);
      const socket = connectChat({
        sessionId: nextSessionId,
        onOpen: () => {
          if (socketRef.current !== socket) {
            return;
          }
          if (!active) {
            return;
          }
          setChatReady(true);
        },
        onMessage: (payload, streamId) => {
          if (socketRef.current !== socket) {
            return;
          }
          if (!active) {
            return;
          }
          handleChatResponse(payload, streamId);
        },
        onTyping: (payload) => {
          if (socketRef.current !== socket) {
            return;
          }
          if (!active) {
            return;
          }
          if (payload.actor === "assistant") {
            setAssistantTyping(payload.isTyping);
          }
        },
        onStreamStart: (payload) => {
          if (socketRef.current !== socket) {
            return;
          }
          if (!active) {
            return;
          }
          handleStreamStart(payload);
        },
        onStreamDelta: (payload) => {
          if (socketRef.current !== socket) {
            return;
          }
          if (!active) {
            return;
          }
          handleStreamDelta(payload);
        },
        onStreamEnd: (payload) => {
          if (socketRef.current !== socket) {
            return;
          }
          if (!active) {
            return;
          }
          handleStreamEnd(payload);
        },
        onSession: (resolvedSessionId) => {
          if (!active) {
            return;
          }
          currentSessionId = resolvedSessionId;
          setStoredSessionId(resolvedSessionId);
          setSessionId(resolvedSessionId);
          void reloadChatHistory(resolvedSessionId);
        },
        onError: (errorMessage) => {
          if (socketRef.current !== socket) {
            return;
          }
          if (!active) {
            return;
          }
          setAssistantTyping(false);
          setChatReady(false);
          setMessage(errorMessage);
        },
        onClose: () => {
          if (socketRef.current !== socket) {
            if (intentionalSocketCloseRef.current) {
              intentionalSocketCloseRef.current = false;
            }
            return;
          }
          socketRef.current = null;
          if (intentionalSocketCloseRef.current) {
            intentionalSocketCloseRef.current = false;
            return;
          }
          if (!active) {
            return;
          }
          setAssistantTyping(false);
          setChatReady(false);
          setMessage("Chat disconnected. Reconnecting...");
          reconnectTimerRef.current = window.setTimeout(() => {
            connectSocket(currentSessionId || nextSessionId);
          }, 1200);
        },
      });
      socketRef.current = socket;
    };
    connectSocketRef.current = connectSocket;

    (async () => {
      try {
        const createdSessionId = await ensureSession();
        if (!active) {
          return;
        }
        currentSessionId = createdSessionId;
        setSessionId(createdSessionId);
        await reloadData();
        await reloadChatHistory(createdSessionId);
        connectSocket(createdSessionId);
      } catch (err) {
        setMessage((err as Error).message);
      }
    })();
    return () => {
      active = false;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (socketRef.current) {
        intentionalSocketCloseRef.current = true;
        socketRef.current.close();
        socketRef.current = null;
      }
      setChatReady(false);
      setAssistantTyping(false);
      connectSocketRef.current = () => undefined;
    };
  }, []);

  useEffect(() => {
    const onPopState = () => {
      setPath(window.location.pathname);
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    if (!selectedProductId) {
      setDetailProduct(null);
      setDetailVariantId("");
      setDetailQuantity(1);
      setDetailLoading(false);
      return;
    }
    let active = true;
    setDetailLoading(true);
    (async () => {
      try {
        const product = await fetchProduct(selectedProductId);
        if (!active) {
          return;
        }
        setDetailProduct(product);
        const firstInStock = product.variants.find((variant) => variant.inStock);
        setDetailVariantId(firstInStock?.id ?? product.variants[0]?.id ?? "");
      } catch (err) {
        if (!active) {
          return;
        }
        setDetailProduct(null);
        setDetailVariantId("");
        setMessage((err as Error).message);
      } finally {
        if (active) {
          setDetailLoading(false);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [selectedProductId]);

  async function onRegister(): Promise<void> {
    setBusy(true);
    setMessage("Creating account...");
    try {
      const payload = await register({ email, password, name });
      const resolvedSessionId = payload.sessionId || sessionId;
      setToken(payload.accessToken);
      if (resolvedSessionId) {
        setStoredSessionId(resolvedSessionId);
        setSessionId(resolvedSessionId);
      }
      setUser(payload.user);
      await reloadData();
      if (resolvedSessionId) {
        await reloadChatHistory(resolvedSessionId);
      }
      if (resolvedSessionId) {
        connectSocketRef.current(resolvedSessionId);
      }
      setMessage("Account created. Guest cart has been attached.");
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onLogin(): Promise<void> {
    setBusy(true);
    setMessage("Signing in...");
    try {
      const payload = await login({ email, password });
      const resolvedSessionId = payload.sessionId || sessionId;
      setToken(payload.accessToken);
      if (resolvedSessionId) {
        setStoredSessionId(resolvedSessionId);
        setSessionId(resolvedSessionId);
      }
      setUser(payload.user);
      await reloadData();
      if (resolvedSessionId) {
        await reloadChatHistory(resolvedSessionId);
      }
      if (resolvedSessionId) {
        connectSocketRef.current(resolvedSessionId);
      }
      setMessage("Signed in. You can now checkout.");
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onAddProduct(product: Product): Promise<void> {
    setBusy(true);
    try {
      const defaultVariant = product.variants.find((variant) => variant.inStock);
      if (!defaultVariant) {
        setMessage("No in-stock variant for this product.");
        return;
      }
      await addToCart({
        productId: product.id,
        variantId: defaultVariant.id,
        quantity: 1,
      });
      const updated = await fetchCart();
      setCart(updated);
      setMessage(`Added ${product.name} to cart.`);
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onAddProductFromDetail(): Promise<void> {
    if (!detailProduct) {
      return;
    }
    if (!detailVariantId) {
      setMessage("No selectable variant for this product.");
      return;
    }
    setBusy(true);
    try {
      await addToCart({
        productId: detailProduct.id,
        variantId: detailVariantId,
        quantity: Math.max(1, detailQuantity),
      });
      const updated = await fetchCart();
      setCart(updated);
      setMessage(`Added ${detailProduct.name} to cart.`);
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onCheckout(): Promise<void> {
    setBusy(true);
    try {
      const payload = await checkout({
        shippingAddress: {
          name: user?.name ?? "Guest User",
          line1: "123 Main St",
          city: "Austin",
          state: "TX",
          postalCode: "78701",
          country: "US",
        },
        paymentMethod: {
          type: "card",
          token: "pm_demo_token",
        },
      });
      await reloadData();
      setMessage(`Order created: ${payload.order.id}`);
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function onSendChat(): void {
    const text = chatInput.trim();
    if (!text || !chatReady || !socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
      return;
    }
    setChatInput("");
    setChatMessages((previous) => [...previous, { role: "user", text }]);
    socketRef.current.send(
      JSON.stringify({
        type: "message",
        payload: { content: text, timestamp: new Date().toISOString(), stream: true, typing: true },
      }),
    );
  }

  function onSuggestedAction(action: string): void {
    let messageText = action;
    if (action.startsWith("search:")) {
      messageText = action.replace("search:", "").replace(/_/g, " ");
    }
    if (action.startsWith("add_to_cart:")) {
      const [, productId, variantId] = action.split(":");
      messageText = `add ${productId} ${variantId} to cart`;
    }
    if (action.startsWith("order_status:")) {
      const [, orderId] = action.split(":");
      messageText = `order status ${orderId}`;
    }
    setChatInput(messageText);
  }

  function onLogout(): void {
    setToken(null);
    setUser(null);
    setMessage("Logged out. You are back in guest mode.");
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <p className="kicker">Omnichannel Agentic Commerce</p>
        <h1>Guest-first shopping. Authenticated checkout.</h1>
        <p className="status" data-testid="status-message">
          {message}
        </p>
        <p className="status" data-testid="session-id">
          Session: {sessionId || "initializing..."}
        </p>
      </header>

      <main className="grid">
        <section className="panel auth-panel" data-testid="auth-panel">
          <h2>{user ? `Signed in as ${user.name}` : "Sign in for checkout"}</h2>
          {!user ? (
            <>
              <label>
                Name
                <input
                  data-testid="name-input"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              </label>
              <label>
                Email
                <input
                  data-testid="email-input"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </label>
              <label>
                Password
                <input
                  data-testid="password-input"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
              <div className="button-row">
                <button data-testid="register-button" disabled={busy} onClick={onRegister}>
                  Register
                </button>
                <button data-testid="login-button" disabled={busy} onClick={onLogin}>
                  Login
                </button>
              </div>
            </>
          ) : (
            <button data-testid="logout-button" disabled={busy} onClick={onLogout}>
              Logout
            </button>
          )}
        </section>

        <section className="panel catalog-panel" data-testid="catalog-panel">
          <div className="panel-header">
            <h2>{selectedProductId ? "Product Details" : "Catalog"}</h2>
            <span>{selectedProductId ? selectedProductId : `${products.length} products`}</span>
          </div>
          {!selectedProductId ? (
            <div className="catalog">
              {products.map((product) => (
                <article className="product-card" key={product.id}>
                  <div className="product-top">
                    <p className="category">{product.category}</p>
                    <p className="price">
                      ${product.price.toFixed(2)} {product.currency}
                    </p>
                  </div>
                  <h3>{product.name}</h3>
                  <p>{product.description}</p>
                  <div className="catalog-actions">
                    <button
                      data-testid={`add-to-cart-${product.id}`}
                      disabled={busy}
                      onClick={() => void onAddProduct(product)}
                    >
                      Add to Cart
                    </button>
                    <button
                      type="button"
                      className="secondary-btn"
                      data-testid={`view-product-${product.id}`}
                      onClick={() => navigateTo(`/products/${encodeURIComponent(product.id)}`)}
                    >
                      View details
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="product-detail-page" data-testid="product-detail-page">
              <button
                type="button"
                className="link-btn"
                data-testid="back-to-catalog"
                onClick={() => navigateTo("/")}
              >
                Back to catalog
              </button>
              {detailLoading && <p className="hint">Loading product details...</p>}
              {!detailLoading && !detailProduct && (
                <p className="hint" data-testid="product-detail-missing">
                  Product not found.
                </p>
              )}
              {!detailLoading && detailProduct && (
                <>
                  <p className="category">{detailProduct.category}</p>
                  <h3 data-testid="product-detail-name">{detailProduct.name}</h3>
                  <p className="product-detail-meta">
                    <span data-testid="product-detail-price">
                      ${detailProduct.price.toFixed(2)} {detailProduct.currency}
                    </span>
                    <span data-testid="product-detail-rating">Rating {detailProduct.rating.toFixed(1)} / 5</span>
                  </p>
                  <p data-testid="product-detail-description">{detailProduct.description}</p>
                  <p className="hint">Product ID: {detailProduct.id}</p>
                  {detailProduct.images[0] && <p className="hint">Image URL: {detailProduct.images[0]}</p>}
                  <div className="detail-controls">
                    <label>
                      Variant
                      <select
                        data-testid="detail-variant-select"
                        value={detailVariantId}
                        onChange={(event) => setDetailVariantId(event.target.value)}
                      >
                        {detailProduct.variants.map((variant) => (
                          <option key={variant.id} value={variant.id}>
                            {variant.size} / {variant.color} ({variant.inStock ? "In stock" : "Out of stock"})
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Quantity
                      <input
                        data-testid="detail-quantity-input"
                        type="number"
                        min={1}
                        max={20}
                        value={detailQuantity}
                        onChange={(event) => {
                          const parsed = Number.parseInt(event.target.value, 10);
                          setDetailQuantity(Number.isFinite(parsed) && parsed > 0 ? parsed : 1);
                        }}
                      />
                    </label>
                  </div>
                  <ul className="variant-list" data-testid="product-detail-variants">
                    {detailProduct.variants.map((variant) => (
                      <li key={variant.id}>
                        <strong>{variant.id}</strong>
                        <span>
                          {variant.size} / {variant.color}
                        </span>
                        <span>{variant.inStock ? "In stock" : "Out of stock"}</span>
                      </li>
                    ))}
                  </ul>
                  <button
                    data-testid="detail-add-to-cart"
                    disabled={busy || !selectedDetailVariant?.inStock}
                    onClick={() => void onAddProductFromDetail()}
                  >
                    Add to Cart
                  </button>
                  {!selectedDetailVariant?.inStock && <p className="hint">Selected variant is out of stock.</p>}
                </>
              )}
            </div>
          )}
        </section>

        <section className="panel cart-panel" data-testid="cart-panel">
          <div className="panel-header">
            <h2>Cart</h2>
            <span data-testid="cart-item-count">{totalItems} items</span>
          </div>
          <ul className="cart-list" data-testid="cart-list">
            {cart.items.map((item) => (
              <li key={item.itemId}>
                <strong>{item.name}</strong>
                <span>
                  {item.quantity} x ${item.price.toFixed(2)}
                </span>
              </li>
            ))}
            {cart.items.length === 0 && <li>Cart is empty.</li>}
          </ul>
          <dl className="totals">
            <div>
              <dt>Subtotal</dt>
              <dd>${cart.subtotal.toFixed(2)}</dd>
            </div>
            <div>
              <dt>Tax</dt>
              <dd>${cart.tax.toFixed(2)}</dd>
            </div>
            <div>
              <dt>Shipping</dt>
              <dd>${cart.shipping.toFixed(2)}</dd>
            </div>
            <div>
              <dt>Total</dt>
              <dd>${cart.total.toFixed(2)}</dd>
            </div>
          </dl>
          <button
            className="checkout"
            data-testid="checkout-button"
            disabled={busy || cart.itemCount === 0}
            onClick={onCheckout}
          >
            Checkout
          </button>
          {!user && <p className="hint">Login is required before order creation.</p>}
        </section>

        <section className="panel chat-panel" data-testid="chat-panel">
          <div className="panel-header">
            <h2>Assistant Chat</h2>
            <span data-testid="chat-message-count">{chatMessages.length} msgs</span>
          </div>
          <p className="hint" data-testid="chat-ready">
            {chatReady ? "connected" : "connecting"}
          </p>
          <div className="chat-log" data-testid="chat-log">
            {chatMessages.length === 0 && (
              <p className="hint">
                Ask: "show me running shoes", "add to cart", "checkout", "order status".
              </p>
            )}
            {chatMessages.map((entry, index) => (
              <div key={`${entry.role}-${entry.streamId ?? index}`} className={`chat-bubble ${entry.role}`}>
                <strong>{entry.role === "user" ? "You" : entry.agent ?? "Assistant"}:</strong>{" "}
                {entry.text}
              </div>
            ))}
            {assistantTyping && <p className="hint">Assistant is typing...</p>}
          </div>
          {chatActions.length > 0 && (
            <div className="chat-actions">
              {chatActions.map((action) => (
                <button
                  key={action.action}
                  type="button"
                  className="action-btn"
                  onClick={() => onSuggestedAction(action.action)}
                >
                  {action.label}
                </button>
              ))}
            </div>
          )}
          <div className="chat-input-row">
            <input
              data-testid="chat-input"
              value={chatInput}
              onChange={(event) => setChatInput(event.target.value)}
              placeholder="Type a shopping request..."
            />
            <button data-testid="chat-send-button" type="button" disabled={busy || !chatReady} onClick={onSendChat}>
              Send
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}
