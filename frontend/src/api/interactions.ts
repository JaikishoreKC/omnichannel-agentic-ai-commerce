import { request } from "./client";
import type { InteractionHistoryMessage } from "../types";

export interface ChatHistoryPayload {
    sessionId: string;
    messages: InteractionHistoryMessage[];
}

export async function fetchChatHistory(input: {
    sessionId?: string;
    limit?: number;
}): Promise<ChatHistoryPayload> {
    const params = new URLSearchParams();
    if (input.sessionId) {
        params.set("sessionId", input.sessionId);
    }
    params.set("limit", String(input.limit ?? 60));
    return request<ChatHistoryPayload>("GET", `/interactions/history?${params.toString()}`);
}
