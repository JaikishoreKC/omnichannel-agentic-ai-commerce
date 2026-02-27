export interface ChatResponsePayload {
    message: string;
    agent: string;
    data: Record<string, unknown>;
    suggestedActions: Array<{ label: string; action: string }>;
    metadata: Record<string, unknown>;
}
