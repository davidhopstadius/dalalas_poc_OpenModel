"""Laddar och validerar konfiguration fran miljon (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_BASE_URL = "https://api.grunden.ai/v1"
DEFAULT_MODEL = "glm-5.1"


class ConfigError(Exception):
    """Kastas nar nodvandig konfiguration saknas."""


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    # Ta forsta ordet sa en ev. inline-kommentar inte forstor tolkningen
    token = value.strip().split(maxsplit=1)[0].lower() if value.strip() else ""
    return token in ("1", "true", "yes", "on", "ja")


@dataclass
class Config:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    system_prompt: str | None = None
    thinking: bool = True
    search: bool = True
    brave_api_key: str | None = None
    # RAG / dokumentsokning
    doc_search: bool = True
    embed_model: str = "bge-m3"
    index_dir: str = "rag_index"
    rag_top_k: int = 5

    @property
    def search_enabled(self) -> bool:
        """Web search ar pa bara om flaggan ar satt OCH en Brave-nyckel finns."""
        return self.search and bool(self.brave_api_key)


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
        thinking=_as_bool(os.getenv("GRUNDEN_THINKING"), default=True),
        search=_as_bool(os.getenv("GRUNDEN_SEARCH"), default=True),
        brave_api_key=os.getenv("BRAVE_API_KEY") or None,
        doc_search=_as_bool(os.getenv("GRUNDEN_DOC_SEARCH"), default=True),
        embed_model=os.getenv("GRUNDEN_EMBED_MODEL", "bge-m3"),
        index_dir=os.getenv("RAG_INDEX_DIR", "rag_index"),
        rag_top_k=int(os.getenv("RAG_TOP_K", "5")),
    )
