from __future__ import annotations

from typing import Any

from openai import APIError, OpenAI

from studio_shift.config import ConfigurationError, load_settings


class ModelClientError(RuntimeError):
    """A safe, user-facing error from the model boundary."""


def call_model(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Any:
    try:
        settings = load_settings()
    except ConfigurationError as exc:
        raise ModelClientError(str(exc)) from exc

    client = OpenAI(
        api_key=settings.api_key,
        base_url=settings.base_url,
        default_headers={"x-data-logging-enabled": "false"},
    )

    try:
        response = client.chat.completions.create(
            model=settings.model_uri,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            parallel_tool_calls=False,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
        )
    except APIError as exc:
        raise ModelClientError(
            "Не удалось обратиться к модели. Проверьте ключ, модель и доступ к сети."
        ) from exc
    except Exception as exc:
        raise ModelClientError("Не удалось подготовить запрос к модели.") from exc

    return response.choices[0].message
