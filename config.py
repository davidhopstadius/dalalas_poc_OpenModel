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
    # Timeout (sek) for API-anrop. Backstop sa appen aldrig hanger oandligt nar
    # Grunden ar seg. Generos default eftersom thinking-svar kan ta lang tid.
    request_timeout: float = 300.0
    # RAG / dokumentsokning
    doc_search: bool = True
    embed_model: str = "bge-m3"
    # Embeddings-backend: "grunden" (API, bge-m3) eller "local" (fastembed,
    # kors i processen). Lokalt gor RAG oberoende av Grundens embeddings-uptime.
    embed_backend: str = "grunden"
    local_embed_model: str = "intfloat/multilingual-e5-large"
    index_dir: str = "rag_index"
    rag_top_k: int = 5
    # Steg 2: reranking (BGE cross-encoder). Slas pa/av i runtime - i CLI med
    # /rerank och i GUI genom att satta config.rerank per fraga.
    rerank: bool = True
    rerank_model: str = "bge-reranker-v2-m3"
    rerank_candidates: int = 20  # antal dense-traffar som skickas till rerankern
    # Rerank-backend: "grunden" (API) eller "local" (fastembed cross-encoder,
    # kors i processen). Lokalt gor reranking oberoende av Grundens uptime.
    rerank_backend: str = "grunden"
    local_rerank_model: str = "jinaai/jina-reranker-v2-base-multilingual"

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
        request_timeout=float(os.getenv("GRUNDEN_TIMEOUT", "300")),
        doc_search=_as_bool(os.getenv("GRUNDEN_DOC_SEARCH"), default=True),
        embed_model=os.getenv("GRUNDEN_EMBED_MODEL", "bge-m3"),
        embed_backend=os.getenv("GRUNDEN_EMBED_BACKEND", "grunden").strip().lower(),
        local_embed_model=os.getenv("GRUNDEN_LOCAL_EMBED_MODEL", "intfloat/multilingual-e5-large"),
        index_dir=os.getenv("RAG_INDEX_DIR", "rag_index"),
        rag_top_k=int(os.getenv("RAG_TOP_K", "5")),
        rerank=_as_bool(os.getenv("GRUNDEN_RERANK"), default=True),
        rerank_model=os.getenv("GRUNDEN_RERANK_MODEL", "bge-reranker-v2-m3"),
        rerank_candidates=int(os.getenv("RAG_RERANK_CANDIDATES", "20")),
        rerank_backend=os.getenv("GRUNDEN_RERANK_BACKEND", "grunden").strip().lower(),
        local_rerank_model=os.getenv("GRUNDEN_LOCAL_RERANK_MODEL", "jinaai/jina-reranker-v2-base-multilingual"),
    )
