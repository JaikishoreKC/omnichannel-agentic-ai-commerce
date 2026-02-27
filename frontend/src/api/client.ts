import type { ChatResponsePayload } from "./types";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/v1";
const WS_BASE = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws";
const SESSION_KEY = "commerce_session_id";
const AUTH_KEY = "commerce_access_token";

type Method = "GET" | "POST" | "PUT" | "DELETE";

export function token(): string | null {
    return localStorage.getItem(AUTH_KEY);
}

export function setToken(value: string | null): void {
    if (value) {
        localStorage.setItem(AUTH_KEY, value);
        return;
    }
    localStorage.removeItem(AUTH_KEY);
}

export function sessionId(): string | null {
    return localStorage.getItem(SESSION_KEY);
}

export { sessionId as currentSessionId };

export function setSessionId(value: string | null): void {
    if (value) {
        localStorage.setItem(SESSION_KEY, value);
        return;
    }
    localStorage.removeItem(SESSION_KEY);
}

export async function request<T>(
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

export function connectChat(params: {
    sessionId: string;
    onMessage: (payload: ChatResponsePayload, streamId?: string) => void;
    onSession: (sessionId: string) => void;
    onError: (message: string) => void;
    onTyping?: (payload: { actor?: string; isTyping: boolean }) => void;
    onStreamStart?: (payload: { streamId: string; agent?: string }) => void;
    onStreamDelta?: (payload: { streamId: string; delta: string }) => void;
    onStreamEnd?: (payload: { streamId: string }) => void;
    onOpen?: () => void;
    onClose?: () => void;
}): WebSocket {
    const socket = new WebSocket(`${WS_BASE}?sessionId=${encodeURIComponent(params.sessionId)}`);
    socket.onopen = () => params.onOpen?.();
    socket.onmessage = (event) => {
        try {
            const parsed = JSON.parse(event.data as string) as {
                type: string;
                sessionId?: string;
                streamId?: string;
                payload?: any;
            };
            if (parsed.type === "session" && parsed.payload?.sessionId) {
                setSessionId(parsed.payload.sessionId);
                params.onSession(parsed.payload.sessionId);
                return;
            }
            if (parsed.type === "typing" && parsed.payload && typeof parsed.payload.isTyping === "boolean") {
                params.onTyping?.({
                    actor: parsed.payload.actor as string | undefined,
                    isTyping: parsed.payload.isTyping as boolean,
                });
                return;
            }
            if (parsed.type === "response" && parsed.payload) {
                params.onMessage(parsed.payload as ChatResponsePayload, parsed.streamId);
                return;
            }
            if (parsed.type === "stream_start" && parsed.payload?.streamId) {
                params.onStreamStart?.({
                    streamId: parsed.payload.streamId as string,
                    agent: parsed.payload.agent as string | undefined,
                });
                return;
            }
            if (parsed.type === "stream_delta" && parsed.payload?.streamId) {
                params.onStreamDelta?.({
                    streamId: parsed.payload.streamId as string,
                    delta: parsed.payload.delta as string,
                });
                return;
            }
            if (parsed.type === "stream_end" && parsed.payload?.streamId) {
                params.onStreamEnd?.({
                    streamId: parsed.payload.streamId as string,
                });
                return;
            }
            if (parsed.type === "error") {
                params.onError(parsed.payload?.message ?? "Unknown websocket error");
            }
        } catch {
            params.onError("Failed to parse websocket message.");
        }
    };
    socket.onerror = () => params.onError("WebSocket connection error.");
    socket.onclose = () => params.onClose?.();
    return socket;
}
