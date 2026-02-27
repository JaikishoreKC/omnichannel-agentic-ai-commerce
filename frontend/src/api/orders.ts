import { request } from "./client";

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
