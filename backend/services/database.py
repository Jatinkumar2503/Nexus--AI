"""SQLite schema and migration helpers for durable NEXUS operational state."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from simulation.models import PlanRecord


def connect(path: Path) -> sqlite3.Connection:
    """Open a database connection with the schema needed by operational stores."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS recovery_plans (
            id TEXT PRIMARY KEY,
            record_json TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS recovery_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            outcome_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS recovery_preferences (
            preference_key TEXT PRIMARY KEY,
            preference_json TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id TEXT NOT NULL,
            actor_role TEXT NOT NULL,
            action TEXT NOT NULL,
            target_id TEXT NOT NULL,
            details_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS execution_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stage TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    return connection


def migrate_legacy_json(database_path: Path, plans_path: Path, memory_path: Path) -> None:
    """Import legacy JSON state once, without overwriting existing database rows."""
    connection = connect(database_path)
    try:
        has_plans = connection.execute("SELECT 1 FROM recovery_plans LIMIT 1").fetchone()
        if not has_plans and plans_path.exists():
            for raw_record in json.loads(plans_path.read_text(encoding="utf-8")):
                record = PlanRecord.model_validate(raw_record)
                connection.execute(
                    "INSERT OR IGNORE INTO recovery_plans (id, record_json) VALUES (?, ?)",
                    (record.id, json.dumps(record.model_dump(mode="json"))),
                )

        has_memory = connection.execute("SELECT 1 FROM recovery_outcomes LIMIT 1").fetchone()
        has_preferences = connection.execute("SELECT 1 FROM recovery_preferences LIMIT 1").fetchone()
        if memory_path.exists() and not (has_memory or has_preferences):
            legacy_memory: dict[str, Any] = json.loads(memory_path.read_text(encoding="utf-8"))
            for outcome in legacy_memory.get("outcomes", []):
                connection.execute(
                    "INSERT INTO recovery_outcomes (outcome_json) VALUES (?)",
                    (json.dumps(outcome),),
                )
            preferences = legacy_memory.get("preferences", {})
            connection.execute(
                "INSERT INTO recovery_preferences (preference_key, preference_json) VALUES (?, ?)",
                ("dispatcher", json.dumps(preferences)),
            )
        connection.commit()
    finally:
        connection.close()
