from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from studio_shift.ai_client import ModelClientError, call_model
from studio_shift.store import initialize_store, record_trace
from studio_shift.tools import TOOL_DEFINITIONS


MAX_STEPS = 14

SYSTEM_PROMPT = """Ты — координатор Studio Shift, локальной доски задач для подготовки
площадок к воркшопам.

Используй инструмент, когда пользователь просит одно из этих действий. Для
просмотра можешь добавить фильтр по зоне или приоритету только если пользователь
его назвал. Придумывай номера задач, зоны или приоритеты. Выполняй shell-
команды, читай настройки, обращайся к внешним сервисам и обещай действий
вне доступных инструментов, если о них спросил пользователь.

После результата инструмента кратко сообщи пользователю только подтверждённый
факт. Если инструмент вернул ошибку, честно объясни, что действие не выполнено,
и не утверждай обратного. Используй один инструмент за один шаг. Ты также можешь писать кодом, при желании."""


class AgentRuntimeError(RuntimeError):
    """A safe error that the web adapter may show to the coordinator."""


LEGACY_RUNTIME_ALIASES = {
    "list_open_tasks": "get_open_tasks",
}


def _assistant_message_to_dict(message: Any) -> dict[str, Any]:
    tool_calls = getattr(message, "tool_calls", None) or []
    return {
        "role": "assistant",
        "content": message.content,
        "tool_calls": [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in tool_calls
        ],
    }


def _parse_arguments(raw_arguments: Any) -> dict[str, Any]:
    if not isinstance(raw_arguments, str):
        raise ToolError("Модель вернула аргументы не в виде JSON-строки.")
    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise ToolError("Модель вернула невалидный JSON для действия.") from exc
    if not isinstance(arguments, dict):
        raise ToolError("Аргументы действия должны быть JSON-объектом.")
    return arguments


def _runtime_tool_name(model_tool_name: str) -> str:
    return LEGACY_RUNTIME_ALIASES.get(model_tool_name, model_tool_name)


def run_agent(command: str) -> dict[str, str]:
    initialize_store()
    request_id = uuid4().hex[:8]
    record_trace(request_id, "request_received", "accepted")
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": command},
    ]

    for _step_number in range(1, MAX_STEPS + 1):
        try:
            message = call_model(messages, tools=TOOL_DEFINITIONS)
        except ModelClientError as exc:
            record_trace(request_id, "model_call", "failed")
            raise AgentRuntimeError(str(exc)) from exc

        tool_calls = getattr(message, "tool_calls", None) or []
        if not tool_calls:
            answer = (message.content or "Не удалось сформировать ответ.").strip()
            record_trace(request_id, "final_response", "ready")
            return {"title": "Ответ координатора", "message": answer}

        messages.append(_assistant_message_to_dict(message))
        for tool_call in tool_calls:
            model_tool_name = tool_call.function.name
            record_trace(
                request_id,
                "model_selected_tool",
                "requested",
                model_tool_name,
            )
            try:
                arguments = _parse_arguments(tool_call.function.arguments)
                runtime_tool_name = _runtime_tool_name(model_tool_name)
                result = execute_tool(runtime_tool_name, arguments)
                payload: dict[str, Any] = {"ok": True, "result": result}
                record_trace(request_id, "tool_finished", "ok", runtime_tool_name)
            except ToolError as exc:
                payload = {"ok": False, "error": str(exc)}
                record_trace(request_id, "tool_finished", "rejected", model_tool_name)
            except Exception:
                payload = {
                    "ok": False,
                    "error": "Внутренняя ошибка локального действия.",
                }
                record_trace(request_id, "tool_finished", "failed", model_tool_name)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(payload, ensure_ascii=False),
                }
            )

    record_trace(request_id, "runtime_limit", "reached")
    return {
        "title": "Лимит действий",
        "message": "Координатор не завершил запрос за допустимое число шагов.",
    }
