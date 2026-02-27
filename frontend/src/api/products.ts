import { request } from "./client";
import type { Product } from "../types";

export async function fetchProducts(): Promise<Product[]> {
    const payload = await request<{ products: Product[] }>("GET", "/products");
    return payload.products;
}

export async function fetchProduct(productId: string): Promise<Product> {
    return request<Product>("GET", `/products/${encodeURIComponent(productId)}`);
}
