from __future__ import annotations

import re
from typing import Any

from studio_shift.store import complete_task, create_task, list_open_tasks


ZONES = ("Северный хвост", "Демо-зона", "Студия", "Склад")
PRIORITIES = ("Обычный", "Высокий")


class ToolError(ValueError):
    """A rejected local action or invalid tool payload."""


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_open_tasks",
            "description": "Возвращает открытые задачи смены с необязательным фильтром по зоне или приоритету.",
            "parameters": {
                "type": "object",
                "properties": {
                    "zone": {"type": "string", "enum": list(ZONES)},
                    "priority": {"type": "string", "enum": list(PRIORITIES)},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_shift_task",
            "description": "Создаёт новую открытую задачу смены с указанной зоной и приоритетом.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "zone": {"type": "string", "enum": list(ZONES)},
                    "priority": {"type": "string", "enum": list(PRIORITIES)},
                },
                "required": ["title", "zone", "priority"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_shift_task",
            "description": "Переводит существующую открытую задачу смены в статус «завершена».",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "pattern": "^SS-[0-9]+$"},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
    },
]


def _require_keys(
    arguments: dict[str, Any],
    required: set[str],
    optional: set[str] | None = None,
) -> None:
    allowed = required | (optional or set())
    missing = required - set(arguments)
    extra = set(arguments) - allowed
    if missing:
        raise ToolError(f"Не хватает полей: {', '.join(sorted(missing))}.")
    if extra:
        raise ToolError(f"Лишние поля: {', '.join(sorted(extra))}.")


def _zone(value: Any) -> str:
    if not isinstance(value, str) or value not in ZONES:
        raise ToolError("Зона должна быть одной из зон Studio Shift.")
    return str(value)


def _priority(value: Any) -> str:
    if not isinstance(value, str) or value not in PRIORITIES:
        raise ToolError("Приоритет должен быть «Обычный» или «Высокий».")
    return str(value)


def _title(value: Any) -> str:
    if not isinstance(value, str):
        raise ToolError("Название задачи должно быть строкой.")
    title = value.strip()
    if not 3 <= len(title) <= 90:
        raise ToolError("Название задачи должно содержать от 3 до 90 символов.")
    return title


def _task_id(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"SS-\d+", value):
        raise ToolError("Номер задачи должен иметь вид SS-123.")
    return value


def execute_tool(tool_name: str, raw_arguments: Any) -> dict[str, Any]:
    arguments = _require_object(raw_arguments)

    if tool_name == "list_open_tasks":
        _require_keys(arguments, set(), {"zone", "priority"})
        zone = _zone(arguments["zone"]) if "zone" in arguments else None
        priority = _priority(arguments["priority"]) if "priority" in arguments else None
        tasks = list_open_tasks(zone=zone, priority=priority)
        return {"count": len(tasks), "tasks": tasks}

    if tool_name == "create_shift_task":
        _require_keys(arguments, {"title", "zone", "priority"})
        task = create_task(
            title=_title(arguments["title"]),
            zone=_zone(arguments["zone"]),
            priority=_priority(arguments["priority"]),
        )
        return {"task": task}

    if tool_name == "complete_shift_task":
        _require_keys(arguments, {"task_id"})
        task = complete_task(_task_id(arguments["task_id"]))
        if task is None:
            raise ToolError("Задача с таким номером не найдена.")
        return {"task": task}

    raise ToolError(f"Действие {tool_name} не разрешено в Studio Shift.")
