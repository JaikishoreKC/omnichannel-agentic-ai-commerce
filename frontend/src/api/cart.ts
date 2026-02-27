import { request } from "./client";
import type { Cart } from "../types";

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
