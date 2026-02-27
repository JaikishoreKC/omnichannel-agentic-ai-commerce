import { request, setSessionId, sessionId } from "./client";

export async function ensureSession(): Promise<string> {
    const existing = sessionId();
    if (existing) {
        try {
            await request<{ id: string }>("GET", `/sessions/${encodeURIComponent(existing)}`);
            return existing;
        } catch {
            setSessionId(null);
        }
    }
    const payload = await request<{ sessionId: string }>("POST", "/sessions", {
        channel: "web",
        initialContext: {},
    });
    setSessionId(payload.sessionId);
    return payload.sessionId;
}
