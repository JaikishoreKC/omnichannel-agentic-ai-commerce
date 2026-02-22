from __future__ import annotations

from abc import ABC, abstractmethod

from app.orchestrator.types import AgentAction, AgentContext, AgentExecutionResult


class BaseAgent(ABC):
    name: str

    @abstractmethod
    def execute(self, action: AgentAction, context: AgentContext) -> AgentExecutionResult:
        raise NotImplementedError

