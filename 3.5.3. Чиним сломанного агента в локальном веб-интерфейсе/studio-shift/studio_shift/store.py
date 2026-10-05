from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "studio_shift.db"
DATABASE_PATH = Path(os.environ.get("STUDIO_SHIFT_DB_PATH", DEFAULT_DATABASE_PATH))

DEFAULT_TASKS = (
    {
        "id": "SS-101",
        "title": "Разложить маркеры по наборам",
        "zone": "Переговорная Север",
        "priority": "Обычный",
        "status": "open",
    },
    {
        "id": "SS-102",
        "title": "Проверить HDMI-переходник",
        "zone": "Демо-зона",
        "priority": "Высокий",
        "status": "open",
    },
    {
        "id": "SS-103",
        "title": "Вернуть кабели в маркированные боксы",
        "zone": "Склад",
        "priority": "Обычный",
        "status": "done",
    },
    {
        "id": "SS-104",
        "title": "Подготовить петличный микрофон",
        "zone": "Студия",
        "priority": "Высокий",
        "status": "open",
    },
)


def _connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def initialize_store() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                zone TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_trace (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                request_id TEXT NOT NULL,
                phase TEXT NOT NULL,
                tool_name TEXT,
                outcome TEXT NOT NULL
            )
            """
        )
        task_count = connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if task_count == 0:
            connection.executemany(
                """
                INSERT INTO tasks (id, title, zone, priority, status, created_at)
                VALUES (:id, :title, :zone, :priority, :status, :created_at)
                """,
                [{**task, "created_at": _now()} for task in DEFAULT_TASKS],
            )


def _row_to_task(row: sqlite3.Row) -> dict[str, str]:
    return {
        "id": row["id"],
        "title": row["title"],
        "zone": row["zone"],
        "priority": row["priority"],
        "status": row["status"],
    }


def list_all_tasks() -> list[dict[str, str]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, title, zone, priority, status
            FROM tasks
            ORDER BY CASE status WHEN 'open' THEN 0 ELSE 1 END, id
            """
        ).fetchall()
    return [_row_to_task(row) for row in rows]


def list_open_tasks(
    zone: str | None = None,
    priority: str | None = None,
) -> list[dict[str, str]]:
    query = "SELECT id, title, zone, priority, status FROM tasks WHERE status = 'open'"
    parameters: list[str] = []
    if zone:
        query += " AND zone = ?"
        parameters.append(zone)
    if priority:
        query += " AND priority = ?"
        parameters.append(priority)
    query += " ORDER BY id"

    with _connect() as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [_row_to_task(row) for row in rows]


def _next_task_id(connection: sqlite3.Connection) -> str:
    rows = connection.execute("SELECT id FROM tasks WHERE id LIKE 'SS-%'").fetchall()
    numbers = [int(row["id"].split("-", 1)[1]) for row in rows]
    return f"SS-{max(numbers, default=100) + 1}"


def _task_to_database_row(task: dict[str, str]) -> dict[str, str]:
    return {
        "id": task["id"],
        "title": task["title"],
        "zone": task["zone"],
        "priority": task.get("urgency", "Обычный"),
        "status": task["status"],
        "created_at": task["created_at"],
    }


def _insert_task(connection: sqlite3.Connection, task: dict[str, str]) -> None:
    connection.execute(
        """
        INSERT INTO tasks (id, title, zone, priority, status, created_at)
        VALUES (:id, :title, :zone, :priority, :status, :created_at)
        """,
        _task_to_database_row(task),
    )


def create_task(title: str, zone: str, priority: str) -> dict[str, str]:
    with _connect() as connection:
        task = {
            "id": _next_task_id(connection),
            "title": title,
            "zone": zone,
            "priority": priority,
            "status": "open",
            "created_at": _now(),
        }
        _insert_task(connection, task)
    return {key: value for key, value in task.items() if key != "created_at"}


def complete_task(task_id: str) -> dict[str, str] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT id, title, zone, priority, status, created_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            return None

        current_task = dict(row)
        completed_task = {**current_task, "status": "done"}
        connection.execute(
            """
            UPDATE tasks
            SET title = :title,
                zone = :zone,
                priority = :priority,
                status = :status
            WHERE id = :id
            """,
            current_task,
        )
    return {key: value for key, value in completed_task.items() if key != "created_at"}


def record_trace(
    request_id: str,
    phase: str,
    outcome: str,
    tool_name: str | None = None,
) -> None:
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO agent_trace (created_at, request_id, phase, tool_name, outcome)
            VALUES (?, ?, ?, ?, ?)
            """,
            (_now(), request_id, phase, tool_name, outcome),
        )


def list_recent_traces(limit: int = 8) -> list[dict[str, str | None]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT created_at, request_id, phase, tool_name, outcome
            FROM agent_trace
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "created_at": row["created_at"].replace("+00:00", "Z"),
            "request_id": row["request_id"],
            "phase": row["phase"],
            "tool_name": row["tool_name"],
            "outcome": row["outcome"],
        }
        for row in rows
    ]
