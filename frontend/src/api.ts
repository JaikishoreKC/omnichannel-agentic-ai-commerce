import type { AuthResponse, Cart, Product } from "./types";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/v1";
const SESSION_KEY = "commerce_session_id";
const AUTH_KEY = "commerce_access_token";

type Method = "GET" | "POST" | "PUT" | "DELETE";

function token(): string | null {
  return localStorage.getItem(AUTH_KEY);
}

export function setToken(value: string | null): void {
  if (value) {
    localStorage.setItem(AUTH_KEY, value);
    return;
  }
  localStorage.removeItem(AUTH_KEY);
}

function sessionId(): string | null {
  return localStorage.getItem(SESSION_KEY);
}

async function request<T>(
  method: Method,
  path: string,
  body?: unknown,
  extraHeaders: Record<string, string> = {},
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...extraHeaders,
  };

  const savedToken = token();
  if (savedToken) {
    headers.Authorization = `Bearer ${savedToken}`;
  }

  const savedSession = sessionId();
  if (savedSession) {
    headers["X-Session-Id"] = savedSession;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      detail = payload.error?.message ?? payload.detail ?? detail;
    } catch {
      // Keep fallback error detail.
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return {} as T;
  }
  return (await response.json()) as T;
}

export async function ensureSession(): Promise<string> {
  const existing = sessionId();
  if (existing) {
    return existing;
  }
  const payload = await request<{ sessionId: string }>("POST", "/sessions", {
    channel: "web",
    initialContext: {},
  });
  localStorage.setItem(SESSION_KEY, payload.sessionId);
  return payload.sessionId;
}

export async function register(input: {
  email: string;
  password: string;
  name: string;
}): Promise<AuthResponse> {
  return request<AuthResponse>("POST", "/auth/register", input);
}

export async function login(input: {
  email: string;
  password: string;
}): Promise<AuthResponse> {
  return request<AuthResponse>("POST", "/auth/login", input);
}

export async function fetchProducts(): Promise<Product[]> {
  const payload = await request<{ products: Product[] }>("GET", "/products");
  return payload.products;
}

export async function fetchCart(): Promise<Cart> {
  return request<Cart>("GET", "/cart");
}

export async function addToCart(input: {
  productId: string;
  variantId: string;
  quantity: number;
}): Promise<void> {
  await request("POST", "/cart/items", input);
}

export async function checkout(input: {
  shippingAddress: {
    name: string;
    line1: string;
    city: string;
    state: string;
    postalCode: string;
    country: string;
  };
  paymentMethod: {
    type: string;
    token: string;
  };
}): Promise<{ order: { id: string } }> {
  const idempotencyKey =
    globalThis.crypto?.randomUUID?.() ?? `web-${Date.now().toString(36)}`;
  return request<{ order: { id: string } }>("POST", "/orders", input, {
    "Idempotency-Key": idempotencyKey,
  });
}

