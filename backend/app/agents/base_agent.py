import asyncio
from abc import ABC, abstractmethod
from typing import AsyncIterator

from app.orchestrator.types import AgentAction, AgentContext, AgentExecutionResult


class BaseAgent(ABC):
    name: str

    @abstractmethod
    def execute(self, action: AgentAction, context: AgentContext) -> AgentExecutionResult:
        raise NotImplementedError

    async def execute_stream(self, action: AgentAction, context: AgentContext) -> AsyncIterator[str]:
        """Default implementation that yields the final message at once."""
        result = await asyncio.to_thread(self.execute, action, context)
        if result.message:
            yield result.message

