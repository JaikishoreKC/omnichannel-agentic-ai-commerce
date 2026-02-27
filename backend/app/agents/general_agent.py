from __future__ import annotations
from typing import AsyncIterator
from app.agents.base_agent import BaseAgent
from app.orchestrator.types import AgentAction, AgentContext, AgentExecutionResult
from app.infrastructure.llm_client import LLMClient

class GeneralAgent(BaseAgent):
    name = "general"

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    def execute(self, action: AgentAction, context: AgentContext) -> AgentExecutionResult:
        # Fallback if streaming is not used
        return AgentExecutionResult(
            success=True,
            message="I'm sorry, I couldn't provide a detailed answer at the moment.",
            data={},
        )

    async def execute_stream(self, action: AgentAction, context: AgentContext) -> AsyncIterator[str]:
        query = str(action.params.get("query", context.initial_intent.get("message", "Internal error"))).strip()
        system_prompt = (
            "You are a helpful commerce assistant for an Omnichannel Brand. "
            "Answer questions about products, orders, or general shopping advice. "
            "Keep it concise and friendly."
        )
        
        async for chunk in self.llm_client.stream_response(
            user_prompt=query,
            system_prompt=system_prompt
        ):
            yield chunk
