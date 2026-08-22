"""Append-only audit log for dispatcher-sensitive operations."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.database import connect


class AuditLog:
    def __init__(self, database_path: Path):
        self._database_path = database_path
        connection = connect(database_path)
        connection.close()

    def record(self, actor_id: str, actor_role: str, action: str, target_id: str, details: dict[str, Any]) -> None:
        connection = connect(self._database_path)
        try:
            connection.execute(
                "INSERT INTO audit_events (actor_id, actor_role, action, target_id, details_json) VALUES (?, ?, ?, ?, ?)",
                (actor_id, actor_role, action, target_id, json.dumps(details)),
            )
            connection.commit()
        finally:
            connection.close()

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        connection = connect(self._database_path)
        try:
            rows = connection.execute(
                "SELECT id, actor_id, actor_role, action, target_id, details_json, created_at FROM audit_events ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            return [
                {"id": row[0], "actor_id": row[1], "actor_role": row[2], "action": row[3], "target_id": row[4], "details": json.loads(row[5]), "created_at": row[6]}
                for row in rows
            ]
        finally:
            connection.close()
