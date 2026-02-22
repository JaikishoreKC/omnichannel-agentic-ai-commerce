import { useEffect, useMemo, useState } from "react";

import {
  addToCart,
  checkout,
  ensureSession,
  fetchCart,
  fetchProducts,
  login,
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

  const totalItems = useMemo(() => cart.itemCount, [cart.itemCount]);

  async function reloadData(): Promise<void> {
    const [productList, cartData] = await Promise.all([fetchProducts(), fetchCart()]);
    setProducts(productList);
    setCart(cartData);
  }

  useEffect(() => {
    (async () => {
      try {
        await ensureSession();
        await reloadData();
      } catch (err) {
        setMessage((err as Error).message);
      }
    })();
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
      </main>
    </div>
  );
}

