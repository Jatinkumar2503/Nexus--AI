"""In-process, bounded execution events for the single-process demo service."""
from __future__ import annotations
from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Deque, Dict, List
from pathlib import Path
from services.database import connect

class ExecutionEventStore:
    def __init__(self, max_events: int = 200):
        self._events: Deque[Dict[str, str]] = deque(maxlen=max_events)
        self._lock = Lock()
        self._sequence = 0
        self._database_path: Path | None = None

    def configure_persistence(self, database_path: Path) -> None:
        self._database_path = database_path

    def emit(self, stage: str, message: str) -> Dict[str, str]:
        with self._lock:
            self._sequence += 1
            event = {"id": str(self._sequence), "stage": stage, "message": message, "timestamp": datetime.now(timezone.utc).isoformat()}
            self._events.append(event)
            if self._database_path:
                connection = connect(self._database_path)
                try:
                    cursor = connection.execute("INSERT INTO execution_events (stage, message) VALUES (?, ?)", (stage, message))
                    event["id"] = str(cursor.lastrowid)
                    connection.commit()
                finally:
                    connection.close()
        return event

    def after(self, event_id: str | None) -> List[Dict[str, str]]:
        if self._database_path:
            connection = connect(self._database_path)
            try:
                lower = int(event_id or 0)
                rows = connection.execute("SELECT id, stage, message, created_at FROM execution_events WHERE id > ? ORDER BY id ASC LIMIT ?", (lower, self._events.maxlen)).fetchall()
                return [{"id": str(row[0]), "stage": row[1], "message": row[2], "timestamp": row[3]} for row in rows]
            finally:
                connection.close()
        with self._lock:
            events = list(self._events)
        if event_id is None:
            return events
        return [event for event in events if int(event["id"]) > int(event_id)]

execution_events = ExecutionEventStore()
