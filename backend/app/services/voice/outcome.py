from __future__ import annotations
from typing import Any

def apply_outcome_actions(
    *,
    call: dict[str, Any],
    voice_service: Any,
    support_service: Any,
    notification_service: Any,
) -> None:
    user_id = str(call.get("userId", "")).strip()
    session_id = str(call.get("sessionId", "")).strip() or "voice-session"
    if not user_id:
        return

    outcome = str(call.get("outcome", "")).strip().lower()
    status = str(call.get("status", "")).strip().lower()

    if outcome in {"do_not_call", "opt_out", "dnc"}:
        voice_service.suppress_user(user_id=user_id, reason="voice_opt_out")
        return

    if outcome in {"requested_callback", "needs_help", "agent_handoff"}:
        support_service.create_ticket(
            user_id=user_id,
            session_id=session_id,
            issue=f"Voice recovery callback requested for cart {call.get('cartId', '')}",
            priority="normal",
        )
        notification_service.send_voice_recovery_followup(
            user_id=user_id,
            call_id=str(call.get("id", "")),
            message="We received your callback request and a support agent will reach out.",
            disposition="callback_requested",
        )
        return

    if outcome in {"converted", "checkout_intent", "interested"}:
        notification_service.send_voice_recovery_followup(
            user_id=user_id,
            call_id=str(call.get("id", "")),
            message="Your cart is still available. Continue checkout when ready.",
            disposition="conversion_intent",
        )
        return

    if status == "failed":
        notification_service.send_voice_recovery_followup(
            user_id=user_id,
            call_id=str(call.get("id", "")),
            message="We could not complete your call. Your cart remains available.",
            disposition="call_failed",
        )
