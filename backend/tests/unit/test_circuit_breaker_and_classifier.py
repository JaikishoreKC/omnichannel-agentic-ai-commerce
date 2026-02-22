from __future__ import annotations

import time

from app.infrastructure.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from app.infrastructure.llm_client import LLMIntentPrediction
from app.orchestrator.intent_classifier import IntentClassifier


class _StubLLMClient:
    def __init__(self, prediction: LLMIntentPrediction | None) -> None:
        self.prediction = prediction

    def classify_intent(self, *, message: str, recent_messages: list[dict[str, object]] | None = None) -> LLMIntentPrediction | None:
        return self.prediction


def test_circuit_breaker_opens_and_recovers() -> None:
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.1)

    def fail() -> int:
        raise RuntimeError("boom")

    for _ in range(2):
        try:
            breaker.call(fail)
        except RuntimeError:
            pass

    assert breaker.snapshot.state == "open"

    try:
        breaker.call(lambda: 1)
    except CircuitBreakerOpenError:
        pass
    else:
        raise AssertionError("Expected CircuitBreakerOpenError while breaker is open")

    time.sleep(0.12)
    assert breaker.call(lambda: 7) == 7
    assert breaker.snapshot.state == "closed"


def test_intent_classifier_prefers_higher_confidence_llm_result() -> None:
    llm_prediction = LLMIntentPrediction(
        intent="checkout",
        confidence=0.82,
        entities={},
    )
    classifier = IntentClassifier(llm_client=_StubLLMClient(llm_prediction))
    result = classifier.classify("please help me complete payment", context={"recent": []})
    assert result.name == "checkout"
    assert result.confidence == 0.82


def test_intent_classifier_detects_search_and_add_combo() -> None:
    classifier = IntentClassifier()
    result = classifier.classify("find running shoes under $150 and add to cart")
    assert result.name == "search_and_add_to_cart"
    assert result.entities["maxPrice"] == 150.0


def test_intent_classifier_detects_discount_code() -> None:
    classifier = IntentClassifier()
    result = classifier.classify("please apply discount code SAVE20")
    assert result.name == "apply_discount"
    assert result.entities["code"] == "SAVE20"


def test_intent_classifier_detects_delayed_order_phrase() -> None:
    classifier = IntentClassifier()
    result = classifier.classify("my order hasn't arrived yet")
    assert result.name == "order_status"
