import { request } from "./client";
import type { Order } from "../types";

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

export async function fetchOrders(): Promise<Order[]> {
    const payload = await request<{ orders: Order[] }>("GET", "/orders");
    return payload.orders;
}
