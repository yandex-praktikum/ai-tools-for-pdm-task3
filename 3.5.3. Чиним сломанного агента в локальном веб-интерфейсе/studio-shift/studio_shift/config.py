from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_URL = "https://ai.api.cloud.yandex.net/v1"
DEFAULT_MODEL_ID = "gpt-oss-1200b"


class ConfigurationError(RuntimeError):
    """Raised when the local model configuration is incomplete."""


@dataclass(frozen=True)
class Settings:
    api_key: str
    model_uri: str
    base_url: str
    temperature: float
    max_tokens: int


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")

    api_key = os.getenv("YANDEX_AI_STUDIO_API_KEY", "").strip()
    folder_id = os.getenv("YANDEX_FOLDER_ID", "").strip()
    model_uri = os.getenv("YANDEX_MODEL_URI", "").strip()
    model_id = os.getenv("YANDEX_MODEL_ID", DEFAULT_MODEL_ID).strip()
    base_url = os.getenv("YANDEX_BASE_URL", DEFAULT_BASE_URL).strip()

    if not model_uri and folder_id:
        model_uri = f"gpt://{folder_id}/{model_id}/latest"

    missing = []
    if not api_key:
        missing.append("YANDEX_AI_STUDIO_API_KEY")
    if not model_uri:
        missing.append("YANDEX_FOLDER_ID или YANDEX_MODEL_URI")
    if missing:
        raise ConfigurationError(
            "Не хватает локальной конфигурации: "
            f"{', '.join(missing)}. Создайте .env по .env.example."
        )

    try:
        temperature = float(os.getenv("YANDEX_TEMPERATURE", "0.2"))
        max_tokens = int(os.getenv("YANDEX_MAX_TOKENS", "700"))
    except ValueError as exc:
        raise ConfigurationError(
            "YANDEX_TEMPERATURE должен быть числом, а YANDEX_MAX_TOKENS — целым."
        ) from exc

    if not 0 <= temperature <= 1:
        raise ConfigurationError("YANDEX_TEMPERATURE должен быть в диапазоне от 0 до 1.")
    if max_tokens <= 0:
        raise ConfigurationError("YANDEX_MAX_TOKENS должен быть больше 0.")

    return Settings(
        api_key=api_key,
        model_uri=model_uri,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
    )
