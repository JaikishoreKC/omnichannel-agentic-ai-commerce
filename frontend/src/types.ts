export interface ProductVariant {
  id: string;
  size: string;
  color: string;
  inStock: boolean;
}

export interface Product {
  id: string;
  name: string;
  description: string;
  category: string;
  price: number;
  currency: string;
  images: string[];
  variants: ProductVariant[];
  rating: number;
}

export interface CartItem {
  itemId: string;
  productId: string;
  variantId: string;
  name: string;
  price: number;
  quantity: number;
  image: string;
}

export interface Cart {
  id: string;
  userId: string | null;
  sessionId: string;
  items: CartItem[];
  subtotal: number;
  tax: number;
  shipping: number;
  discount: number;
  total: number;
  itemCount: number;
  currency: string;
}

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: string;
  createdAt: string;
}

export interface AuthResponse {
  user: AuthUser;
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  sessionId?: string;
}

export interface InteractionHistoryMessage {
  id: string;
  sessionId: string;
  userId: string | null;
  message: string;
  intent: string;
  agent: string;
  response: {
    message?: string;
    agent?: string;
    [key: string]: unknown;
  };
  timestamp: string;
}
