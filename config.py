"""Laddar och validerar konfiguration fran miljon (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_BASE_URL = "https://api.grunden.ai/v1"
DEFAULT_MODEL = "glm-5.1"


class ConfigError(Exception):
    """Kastas nar nodvandig konfiguration saknas."""


@dataclass
class Config:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    system_prompt: str | None = None


def load_config() -> Config:
    """Las konfiguration fran .env / miljovariabler.

    Kastar ConfigError med ett tydligt meddelande om API-nyckeln saknas.
    """
    load_dotenv()

    api_key = os.getenv("GRUNDEN_API_KEY")
    if not api_key:
        raise ConfigError(
            "GRUNDEN_API_KEY saknas. Kopiera .env.example till .env och fyll i din nyckel:\n"
            "    copy .env.example .env"
        )

    return Config(
        api_key=api_key,
        base_url=os.getenv("GRUNDEN_BASE_URL", DEFAULT_BASE_URL),
        model=os.getenv("GRUNDEN_MODEL", DEFAULT_MODEL),
        system_prompt=os.getenv("GRUNDEN_SYSTEM_PROMPT") or None,
    )
