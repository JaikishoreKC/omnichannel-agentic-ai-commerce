import { useEffect, useMemo, useRef, useState } from "react";

import {
  addToCart,
  checkout,
  connectChat,
  ensureSession,
  fetchCart,
  fetchProducts,
  login,
  type ChatResponsePayload,
  register,
  setToken,
} from "./api";
import type { AuthUser, Cart, Product } from "./types";

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
  const [chatMessages, setChatMessages] = useState<
    Array<{ role: "user" | "assistant"; text: string; agent?: string }>
  >([]);
  const [chatActions, setChatActions] = useState<Array<{ label: string; action: string }>>([]);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);

  const totalItems = useMemo(() => cart.itemCount, [cart.itemCount]);

  async function reloadData(): Promise<void> {
    const [productList, cartData] = await Promise.all([fetchProducts(), fetchCart()]);
    setProducts(productList);
    setCart(cartData);
  }

  function handleChatResponse(payload: ChatResponsePayload): void {
    setChatMessages((previous) => [
      ...previous,
      { role: "assistant", text: payload.message, agent: payload.agent },
    ]);
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

  useEffect(() => {
    let active = true;
    let currentSessionId = "";

    const connectSocket = (nextSessionId: string) => {
      if (!active) {
        return;
      }
      if (socketRef.current) {
        socketRef.current.close();
      }
      const socket = connectChat({
        sessionId: nextSessionId,
        onMessage: (payload) => {
          if (!active) {
            return;
          }
          handleChatResponse(payload);
        },
        onSession: (resolvedSessionId) => {
          if (!active) {
            return;
          }
          currentSessionId = resolvedSessionId;
          setSessionId(resolvedSessionId);
        },
        onError: (errorMessage) => {
          if (!active) {
            return;
          }
          setMessage(errorMessage);
        },
        onClose: () => {
          socketRef.current = null;
          if (!active) {
            return;
          }
          setMessage("Chat disconnected. Reconnecting...");
          reconnectTimerRef.current = window.setTimeout(() => {
            connectSocket(currentSessionId || nextSessionId);
          }, 1200);
        },
      });
      socketRef.current = socket;
    };

    (async () => {
      try {
        const createdSessionId = await ensureSession();
        if (!active) {
          return;
        }
        currentSessionId = createdSessionId;
        setSessionId(createdSessionId);
        await reloadData();
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
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, []);

  async function onRegister(): Promise<void> {
    setBusy(true);
    setMessage("Creating account...");
    try {
      const payload = await register({ email, password, name });
      setToken(payload.accessToken);
      setUser(payload.user);
      await reloadData();
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
      setToken(payload.accessToken);
      setUser(payload.user);
      await reloadData();
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
    if (!text || !socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
      return;
    }
    setChatInput("");
    setChatMessages((previous) => [...previous, { role: "user", text }]);
    socketRef.current.send(
      JSON.stringify({
        type: "message",
        payload: { content: text, timestamp: new Date().toISOString() },
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
        <p className="status">{message}</p>
        <p className="status">Session: {sessionId || "initializing..."}</p>
      </header>

      <main className="grid">
        <section className="panel auth-panel">
          <h2>{user ? `Signed in as ${user.name}` : "Sign in for checkout"}</h2>
          {!user ? (
            <>
              <label>
                Name
                <input value={name} onChange={(event) => setName(event.target.value)} />
              </label>
              <label>
                Email
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </label>
              <label>
                Password
                <input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
              <div className="button-row">
                <button disabled={busy} onClick={onRegister}>
                  Register
                </button>
                <button disabled={busy} onClick={onLogin}>
                  Login
                </button>
              </div>
            </>
          ) : (
            <button disabled={busy} onClick={onLogout}>
              Logout
            </button>
          )}
        </section>

        <section className="panel catalog-panel">
          <div className="panel-header">
            <h2>Catalog</h2>
            <span>{products.length} products</span>
          </div>
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
                <button disabled={busy} onClick={() => void onAddProduct(product)}>
                  Add to Cart
                </button>
              </article>
            ))}
          </div>
        </section>

        <section className="panel cart-panel">
          <div className="panel-header">
            <h2>Cart</h2>
            <span>{totalItems} items</span>
          </div>
          <ul className="cart-list">
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
          <button className="checkout" disabled={busy || cart.itemCount === 0} onClick={onCheckout}>
            Checkout
          </button>
          {!user && <p className="hint">Login is required before order creation.</p>}
        </section>

        <section className="panel chat-panel">
          <div className="panel-header">
            <h2>Assistant Chat</h2>
            <span>{chatMessages.length} msgs</span>
          </div>
          <div className="chat-log">
            {chatMessages.length === 0 && (
              <p className="hint">
                Ask: "show me running shoes", "add to cart", "checkout", "order status".
              </p>
            )}
            {chatMessages.map((entry, index) => (
              <div key={`${entry.role}-${index}`} className={`chat-bubble ${entry.role}`}>
                <strong>{entry.role === "user" ? "You" : entry.agent ?? "Assistant"}:</strong>{" "}
                {entry.text}
              </div>
            ))}
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
              value={chatInput}
              onChange={(event) => setChatInput(event.target.value)}
              placeholder="Type a shopping request..."
            />
            <button type="button" disabled={busy} onClick={onSendChat}>
              Send
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}
