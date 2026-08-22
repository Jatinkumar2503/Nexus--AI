"""SQLite-backed store for approved recovery outcomes and preferences."""
from __future__ import annotations
import json
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List
from services.database import connect

class RecoveryMemory:
    def __init__(self, path: Path):
        self.path, self.lock = path, Lock()
        connection = connect(path)
        connection.close()

    def record_outcome(self, outcome: Dict[str, Any]) -> None:
        with self.lock:
            connection = connect(self.path)
            try:
                connection.execute("INSERT INTO recovery_outcomes (outcome_json) VALUES (?)", (json.dumps(outcome),))
                connection.commit()
            finally:
                connection.close()

    def outcomes(self) -> List[Dict[str, Any]]:
        with self.lock:
            connection = connect(self.path)
            try:
                return [json.loads(row[0]) for row in connection.execute("SELECT outcome_json FROM recovery_outcomes ORDER BY id")]
            finally:
                connection.close()

    def preferences(self) -> Dict[str, Any]:
        with self.lock:
            connection = connect(self.path)
            try:
                row = connection.execute("SELECT preference_json FROM recovery_preferences WHERE preference_key = ?", ("dispatcher",)).fetchone()
                return json.loads(row[0]) if row else {}
            finally:
                connection.close()

    def set_preferences(self, preferences: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            connection = connect(self.path)
            try:
                connection.execute(
                    """INSERT INTO recovery_preferences (preference_key, preference_json) VALUES (?, ?)
                    ON CONFLICT(preference_key) DO UPDATE SET preference_json=excluded.preference_json, updated_at=CURRENT_TIMESTAMP""",
                    ("dispatcher", json.dumps(preferences)),
                )
                connection.commit()
                return preferences
            finally:
                connection.close()
