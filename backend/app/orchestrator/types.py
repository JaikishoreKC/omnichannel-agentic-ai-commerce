from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IntentResult:
    name: str
    confidence: float
    entities: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentAction:
    name: str
    params: dict[str, Any] = field(default_factory=dict)
    target_agent: str | None = None


@dataclass
class AgentContext:
    session_id: str
    user_id: str | None
    channel: str
    session: dict[str, Any]
    cart: dict[str, Any] | None
    preferences: dict[str, Any] | None
    memory: dict[str, Any] | None = None
    recent_messages: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentExecutionResult:
    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    next_actions: list[dict[str, str]] = field(default_factory=list)


@dataclass
class AgentResponse:
    message: str
    agent: str
    data: dict[str, Any]
    suggested_actions: list[dict[str, str]]
    metadata: dict[str, Any]
