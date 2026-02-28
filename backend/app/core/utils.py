from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def iso_now() -> str:
    return utc_now().isoformat()

def generate_id(prefix: str) -> str:
    """Generates a unique ID with the given prefix."""
    # Use 12 characters of UUID to be reasonably short but very unlikely to collide
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def default_session_expiry(minutes: int = 30) -> str:
    return (utc_now() + timedelta(minutes=minutes)).isoformat()
