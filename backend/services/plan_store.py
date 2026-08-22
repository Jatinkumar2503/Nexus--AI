"""SQLite-backed lifecycle store for recovery plans."""
import json
from pathlib import Path
from threading import Lock
from simulation.models import PlanRecord
from services.database import connect

class PlanStore:
    def __init__(self, path: Path):
        self._path = path
        self._lock = Lock()
        connection = connect(path)
        connection.close()

    def save(self, record: PlanRecord) -> PlanRecord:
        with self._lock:
            connection = connect(self._path)
            try:
                connection.execute(
                    """INSERT INTO recovery_plans (id, record_json) VALUES (?, ?)
                    ON CONFLICT(id) DO UPDATE SET record_json=excluded.record_json, updated_at=CURRENT_TIMESTAMP""",
                    (record.id, json.dumps(record.model_dump(mode="json"))),
                )
                connection.commit()
            finally:
                connection.close()
            return record

    def get(self, plan_id: str) -> PlanRecord | None:
        with self._lock:
            connection = connect(self._path)
            try:
                row = connection.execute("SELECT record_json FROM recovery_plans WHERE id = ?", (plan_id,)).fetchone()
                return PlanRecord.model_validate_json(row[0]) if row else None
            finally:
                connection.close()

    def transition(self, plan_id: str, expected_status: str, next_status: str, validation=None) -> PlanRecord | None:
        """Atomically advance one lifecycle state, returning None on a stale transition."""
        with self._lock:
            connection = connect(self._path)
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute("SELECT record_json FROM recovery_plans WHERE id = ?", (plan_id,)).fetchone()
                if not row:
                    connection.rollback()
                    return None
                record = PlanRecord.model_validate_json(row[0])
                if record.status != expected_status:
                    connection.rollback()
                    return None
                record.status = next_status
                if validation is not None:
                    record.validation = validation
                connection.execute("UPDATE recovery_plans SET record_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (json.dumps(record.model_dump(mode="json")), plan_id))
                connection.commit()
                return record
            finally:
                connection.close()
