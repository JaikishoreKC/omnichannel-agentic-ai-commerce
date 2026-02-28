from __future__ import annotations

from copy import deepcopy
import hashlib
import hmac
import json
from typing import Any

from app.core.config import Settings
from app.repositories.admin_activity_repository import AdminActivityRepository
from app.core.utils import generate_id, iso_now


class AdminActivityService:
    def __init__(
        self,
        *,
        settings: Settings,
        admin_activity_repository: AdminActivityRepository,
    ) -> None:
        self.settings = settings
        self.admin_activity_repository = admin_activity_repository

    def record(
        self,
        *,
        admin_user: dict[str, Any],
        action: str,
        resource: str,
        resource_id: str,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        previous_hash = ""
        latest = self.admin_activity_repository.get_latest()
        if latest:
            previous_hash = str(latest.get("entryHash", "")).strip()

        payload = {
            "id": generate_id("admin_log"),
            "adminId": str(admin_user.get("id", "")),
            "adminEmail": str(admin_user.get("email", "")),
            "action": action,
            "resource": resource,
            "resourceId": resource_id,
            "changes": {
                "before": deepcopy(before) if isinstance(before, dict) else None,
                "after": deepcopy(after) if isinstance(after, dict) else None,
            },
            "ipAddress": ip_address or "",
            "userAgent": user_agent or "",
            "timestamp": iso_now(),
            "prevHash": previous_hash,
            "hashVersion": "v1",
        }
        payload["entryHash"] = self._compute_entry_hash(payload)
        return self.admin_activity_repository.create(payload)

    def list_recent(self, *, limit: int = 100) -> dict[str, Any]:
        return {"logs": self.admin_activity_repository.list_recent(limit=limit)}

    def verify_integrity(self, *, limit: int = 5000) -> dict[str, Any]:
        safe_limit = max(1, min(limit, 10000))
        logs = self.admin_activity_repository.list_recent(limit=safe_limit)
        # list_recent returns them sorted DESC by timestamp. 
        # For verification, we likely want them ASC if we're chaining hashes.
        logs.reverse()

        if not logs:
            return {"ok": True, "total": 0, "issues": []}

        issues: list[dict[str, Any]] = []
        expected_prev = ""
        # Note: If we only have the last N logs, we can't verify the very first one's prevHash if it was non-empty.
        # But for now let's assume if it's the start of our check, we might not know the exact expected_prev.
        # However, if we start from the very beginning of the collection, expected_prev = "".
        # For a partial list, this check might fail on the first element.
        for i, row in enumerate(logs):
            row_id = str(row.get("id", "")).strip()
            prev_hash = str(row.get("prevHash", "")).strip()
            entry_hash = str(row.get("entryHash", "")).strip()
            
            if i == 0 and prev_hash != "":
                 # If it's a sliding window check, we might need to skip prevHash check for the first element
                 # OR fetch the one before it.
                 pass
            elif prev_hash != expected_prev:
                issues.append(
                    {
                        "id": row_id,
                        "error": "prev_hash_mismatch",
                        "expectedPrevHash": expected_prev,
                        "actualPrevHash": prev_hash,
                    }
                )
            expected_entry = self._compute_entry_hash(row)
            if not entry_hash:
                issues.append({"id": row_id, "error": "missing_entry_hash"})
            elif entry_hash != expected_entry:
                issues.append(
                    {
                        "id": row_id,
                        "error": "entry_hash_mismatch",
                    }
                )
            expected_prev = entry_hash

        return {
            "ok": len(issues) == 0,
            "total": len(logs),
            "issues": issues,
        }

    def _compute_entry_hash(self, payload: dict[str, Any]) -> str:
        canonical = json.dumps(
            {
                "id": str(payload.get("id", "")),
                "adminId": str(payload.get("adminId", "")),
                "adminEmail": str(payload.get("adminEmail", "")),
                "action": str(payload.get("action", "")),
                "resource": str(payload.get("resource", "")),
                "resourceId": str(payload.get("resourceId", "")),
                "changes": deepcopy(payload.get("changes")),
                "ipAddress": str(payload.get("ipAddress", "")),
                "userAgent": str(payload.get("userAgent", "")),
                "timestamp": str(payload.get("timestamp", "")),
                "prevHash": str(payload.get("prevHash", "")),
                "hashVersion": str(payload.get("hashVersion", "v1")),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        secret = str(self.settings.token_secret or "").strip() or "replace-with-strong-secret"
        return hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
