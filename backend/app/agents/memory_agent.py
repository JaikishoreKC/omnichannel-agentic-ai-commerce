from __future__ import annotations

from typing import Any

from app.agents.base_agent import BaseAgent
from app.orchestrator.types import AgentAction, AgentContext, AgentExecutionResult
from app.services.memory_service import MemoryService


class MemoryAgent(BaseAgent):
    name = "memory"

    def __init__(self, memory_service: MemoryService) -> None:
        self.memory_service = memory_service

    def execute(self, action: AgentAction, context: AgentContext) -> AgentExecutionResult:
        user_id = context.user_id
        if not user_id:
            return AgentExecutionResult(
                success=False,
                message="Sign in first and then I can remember your preferences across sessions.",
                data={"code": "AUTH_REQUIRED"},
            )

        if action.name == "show_memory":
            summary = self.memory_service.summarize_memory(user_id=user_id)
            return AgentExecutionResult(
                success=True,
                message="Here is what I currently remember about your shopping preferences.",
                data=summary,
                next_actions=[
                    {"label": "Recommend for me", "action": "search:something for me"},
                    {"label": "Clear memory", "action": "clear memory"},
                ],
            )

        if action.name == "save_preference":
            updates = action.params.get("updates", {})
            if not isinstance(updates, dict) or not updates:
                return AgentExecutionResult(
                    success=False,
                    message="Tell me what to remember, for example: remember I like denim and size M.",
                    data={},
                )
            saved = self.memory_service.save_preference_updates(user_id=user_id, updates=updates)
            highlights = self._highlights_from_updates(updates)
            message = "Saved your preferences."
            if highlights:
                message = f"Saved your preferences: {', '.join(highlights)}."
            return AgentExecutionResult(
                success=True,
                message=message,
                data=saved,
                next_actions=[
                    {"label": "Show memory", "action": "show memory"},
                    {"label": "Recommend now", "action": "recommend something"},
                ],
            )

        if action.name == "forget_preference":
            key = str(action.params.get("key", "")).strip() or None
            value = str(action.params.get("value", "")).strip() or None
            cleared = self.memory_service.forget_preference(user_id=user_id, key=key, value=value)
            subject = value or key or "selected preference"
            return AgentExecutionResult(
                success=True,
                message=f"Forgot {subject}.",
                data=cleared,
                next_actions=[{"label": "Show memory", "action": "show memory"}],
            )

        if action.name == "clear_memory":
            self.memory_service.clear_memory(user_id=user_id)
            return AgentExecutionResult(
                success=True,
                message="Cleared your saved memory and preference history.",
                data={"success": True},
            )

        return AgentExecutionResult(
            success=False,
            message=f"Unsupported memory action: {action.name}",
            data={},
        )

    def _highlights_from_updates(self, updates: dict[str, Any]) -> list[str]:
        highlights: list[str] = []
        size = updates.get("size")
        if isinstance(size, str) and size.strip():
            highlights.append(f"size {size.strip()}")

        price = updates.get("priceRange")
        if isinstance(price, dict):
            minimum = price.get("min")
            maximum = price.get("max")
            if minimum not in (None, 0, 0.0):
                highlights.append(f"min budget ${float(minimum):.0f}")
            if maximum not in (None, 0, 0.0):
                highlights.append(f"max budget ${float(maximum):.0f}")

        for field, label in (
            ("categories", "categories"),
            ("stylePreferences", "styles"),
            ("colorPreferences", "colors"),
            ("brandPreferences", "brands"),
        ):
            raw = updates.get(field)
            if not isinstance(raw, list):
                continue
            cleaned = [str(item).strip().lower() for item in raw if str(item).strip()]
            if cleaned:
                highlights.append(f"{label} {', '.join(cleaned)}")
        return highlights
