from __future__ import annotations

from app.orchestrator.types import AgentExecutionResult, AgentResponse, IntentResult


class ResponseFormatter:
    def format(
        self,
        *,
        result: AgentExecutionResult,
        intent: IntentResult,
        agent_name: str,
    ) -> AgentResponse:
        return AgentResponse(
            message=result.message,
            agent=agent_name,
            data=result.data,
            suggested_actions=result.next_actions,
            metadata={
                "intent": intent.name,
                "confidence": intent.confidence,
                "success": result.success,
            },
        )

