from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any

from app.agents.base_agent import BaseAgent
from app.orchestrator.action_extractor import ActionExtractor
from app.orchestrator.agent_router import AgentRouter
from app.orchestrator.context_builder import ContextBuilder
from app.orchestrator.intent_classifier import IntentClassifier
from app.orchestrator.response_formatter import ResponseFormatter
from app.orchestrator.types import AgentExecutionResult, AgentResponse
from app.services.interaction_service import InteractionService
from app.services.memory_service import MemoryService


class Orchestrator:
    def __init__(
        self,
        *,
        intent_classifier: IntentClassifier,
        context_builder: ContextBuilder,
        action_extractor: ActionExtractor,
        router: AgentRouter,
        formatter: ResponseFormatter,
        interaction_service: InteractionService,
        memory_service: MemoryService,
        agents: dict[str, BaseAgent],
    ) -> None:
        self.intent_classifier = intent_classifier
        self.context_builder = context_builder
        self.action_extractor = action_extractor
        self.router = router
        self.formatter = formatter
        self.interaction_service = interaction_service
        self.memory_service = memory_service
        self.agents = agents

    async def process_message(
        self,
        *,
        message: str,
        session_id: str,
        user_id: str | None,
        channel: str,
    ) -> dict[str, Any]:
        recent = self.interaction_service.recent(session_id=session_id, limit=12)
        intent = self.intent_classifier.classify(message=message, context={"recent": recent})
        context = self.context_builder.build(
            intent=intent,
            session_id=session_id,
            user_id=user_id,
            channel=channel,
            recent_messages=recent,
        )
        actions = self.action_extractor.extract(intent)
        route_agent_name = self.router.route(intent)
        if len(actions) == 1:
            action = actions[0]
            agent_name = action.target_agent or route_agent_name
            agent = self.agents[agent_name]
            result = agent.execute(action=action, context=context)
        else:
            result, agent_name = await self._execute_multi_action(
                route_agent_name=route_agent_name,
                actions=actions,
                context=context,
            )

        response: AgentResponse = self.formatter.format(
            result=result,
            intent=intent,
            agent_name=agent_name,
        )
        payload = self._to_transport_payload(response)

        self.interaction_service.record(
            session_id=context.session_id,
            user_id=context.user_id,
            message=message,
            intent=intent.name,
            agent=agent_name,
            response=payload,
        )
        self.context_builder.session_service.update_conversation(
            session_id=context.session_id,
            last_intent=intent.name,
            last_agent=agent_name,
            last_message=message,
            entities=intent.entities,
        )
        asyncio.create_task(
            self._record_memory(
                user_id=context.user_id,
                intent=intent.name,
                message=message,
                response=payload,
            )
        )

        return payload

    async def _record_memory(
        self,
        *,
        user_id: str | None,
        intent: str,
        message: str,
        response: dict[str, Any],
    ) -> None:
        await asyncio.to_thread(
            self.memory_service.record_interaction,
            user_id=user_id,
            intent=intent,
            message=message,
            response=response,
        )

    async def _execute_multi_action(
        self,
        *,
        route_agent_name: str,
        actions: list[Any],
        context: Any,
    ) -> tuple[AgentExecutionResult, str]:
        async def run_action(action: Any) -> tuple[str, AgentExecutionResult]:
            agent_name = action.target_agent or route_agent_name
            agent = self.agents[agent_name]
            result = await asyncio.to_thread(agent.execute, action, context)
            return agent_name, result

        pairs = await asyncio.gather(*(run_action(action) for action in actions))
        combined_data: dict[str, Any] = {}
        messages: list[str] = []
        suggested: list[dict[str, str]] = []
        success = True
        for agent_name, result in pairs:
            combined_data[agent_name] = result.data
            messages.append(result.message)
            suggested.extend(result.next_actions)
            success = success and result.success

        return (
            AgentExecutionResult(
                success=success,
                message=" ".join(messages),
                data=combined_data,
                next_actions=suggested[:6],
            ),
            "orchestrator",
        )

    def _to_transport_payload(self, response: AgentResponse) -> dict[str, Any]:
        payload = asdict(response)
        return {
            "message": payload["message"],
            "agent": payload["agent"],
            "data": payload["data"],
            "suggestedActions": payload["suggested_actions"],
            "metadata": payload["metadata"],
        }
