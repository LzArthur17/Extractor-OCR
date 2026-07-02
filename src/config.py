from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "API Extrator CRLV"
    app_version: str = "1.0.0"
    cors_origins: tuple[str, ...] = ("*",)
    default_ollama_model: str = "llama3.1"
    ollama_url: str = "http://localhost:11434"
    review_min_score: int = 90
    max_pages: int = 1
    retry_min_score: int = 85
    ocr_retry_timeout_seconds: int = 12
    enable_ocr_retry: bool = True


def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "API Extrator CRLV"),
        app_version=os.getenv("APP_VERSION", "1.0.0"),
        cors_origins=_parse_csv(os.getenv("CORS_ORIGINS", "*")),
        default_ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1"),
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        review_min_score=_parse_int(os.getenv("REVIEW_MIN_SCORE"), default=90),
        max_pages=_parse_int(os.getenv("MAX_PAGES"), default=1),
        retry_min_score=_parse_int(os.getenv("RETRY_MIN_SCORE"), default=85),
        ocr_retry_timeout_seconds=_parse_int(os.getenv("OCR_RETRY_TIMEOUT_SECONDS"), default=12),
        enable_ocr_retry=_parse_bool(os.getenv("ENABLE_OCR_RETRY"), default=True),
    )


def _parse_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip()) or ("*",)


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}
