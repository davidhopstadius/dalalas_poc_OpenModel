"""Laddar och validerar konfiguration fran miljon (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_BASE_URL = "https://api.grunden.ai/v1"
DEFAULT_MODEL = "glm-5.1"

# Leverantorer som appen kan koppla mot. grunden/berget ar OpenAI-kompatibla,
# anthropic anvander Messages-API:t (egen adapter i chat.py).
DEFAULT_BERGET_BASE_URL = "https://api.berget.ai/v1"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"


# Anslutning for den aktiva leverantoren - vad chat.py behover for att koppla.
# kind: "openai" (Grunden/Berget) eller "anthropic" (egen adapter).
@dataclass
class LLMConnection:
    kind: str
    model: str
    api_key: str
    base_url: str | None = None


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
    # leverantoren ar seg. Sankt fran 300 -> 120 sa en trog leverantor felar
    # synligt i stallet for att hanga i minuter (thinking-svar ryms anda).
    request_timeout: float = 120.0
    # ---- Leverantorsval (multi-provider) -------------------------------------
    # Aktiv leverantor: "grunden" (default, oforandrat beteende), "berget" eller
    # "anthropic". base_url/model/api_key ovan ar Grundens falt (bakatkompatibelt).
    provider: str = "grunden"
    # Berget (OpenAI-kompatibel, svensk/EU). Pris gomt bakom inloggning -> editbart.
    berget_base_url: str = DEFAULT_BERGET_BASE_URL
    berget_model: str = ""
    berget_api_key: str | None = None
    berget_price_in: float = 0.0   # kr per 1M in-tokens (fylls i av anvandaren)
    berget_price_out: float = 0.0  # kr per 1M ut-tokens
    # Anthropic (Messages-API, egen adapter). max_tokens ar obligatoriskt dar.
    anthropic_model: str = DEFAULT_ANTHROPIC_MODEL
    anthropic_api_key: str | None = None
    anthropic_max_tokens: int = 8000
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

    def active_llm(self) -> LLMConnection:
        """Anslutningen for den aktiva leverantoren (vad chat.py kopplar mot)."""
        if self.provider == "berget":
            return LLMConnection(
                kind="openai",
                model=self.berget_model,
                api_key=self.berget_api_key or "",
                base_url=self.berget_base_url,
            )
        if self.provider == "anthropic":
            return LLMConnection(
                kind="anthropic",
                model=self.anthropic_model,
                api_key=self.anthropic_api_key or "",
            )
        # grunden (default) - befintliga falt, oforandrat beteende.
        return LLMConnection(
            kind="openai",
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
        )


def load_config() -> Config:
    """Las konfiguration fran .env / miljovariabler.

    Kastar ConfigError med ett tydligt meddelande om API-nyckeln saknas.
    """
    load_dotenv()

    provider = os.getenv("LLM_PROVIDER", "grunden").strip().lower() or "grunden"
    api_key = os.getenv("GRUNDEN_API_KEY")

    cfg = Config(
        api_key=api_key or "",
        base_url=os.getenv("GRUNDEN_BASE_URL", DEFAULT_BASE_URL),
        model=os.getenv("GRUNDEN_MODEL", DEFAULT_MODEL),
        system_prompt=os.getenv("GRUNDEN_SYSTEM_PROMPT") or None,
        thinking=_as_bool(os.getenv("GRUNDEN_THINKING"), default=True),
        search=_as_bool(os.getenv("GRUNDEN_SEARCH"), default=True),
        brave_api_key=os.getenv("BRAVE_API_KEY") or None,
        request_timeout=float(os.getenv("GRUNDEN_TIMEOUT", "120")),
        provider=provider,
        berget_base_url=os.getenv("BERGET_BASE_URL", DEFAULT_BERGET_BASE_URL),
        berget_model=os.getenv("BERGET_MODEL", ""),
        berget_api_key=os.getenv("BERGET_API_KEY") or None,
        berget_price_in=float(os.getenv("BERGET_PRICE_IN", "0") or 0),
        berget_price_out=float(os.getenv("BERGET_PRICE_OUT", "0") or 0),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
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

    # Krav: den AKTIVA leverantoren maste ha en nyckel. Andra leverantorer far
    # sakna nyckel (de aktiveras forst nar man valjer dem och fyller i nyckeln).
    if not cfg.active_llm().api_key:
        names = {
            "grunden": "GRUNDEN_API_KEY",
            "berget": "BERGET_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        var = names.get(provider, "GRUNDEN_API_KEY")
        raise ConfigError(
            f"{var} saknas for vald leverantor ({provider}). Kopiera .env.example "
            "till .env och fyll i nyckeln, eller satt den under Installningar:\n"
            "    copy .env.example .env"
        )

    return cfg
