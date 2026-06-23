"""Bygger en effektiv Config (env + sparade overrides) for varje anrop.

Sa kan GUI:t andra installningar live utan omstart - varje fraga laser de
senaste vardena. Hemliga nycklar kan komma antingen fran .env eller fran
overrides (satta via installningssidan).
"""
from __future__ import annotations

from dotenv import load_dotenv

from config import Config, ConfigError, load_config
from server import settings_store


def effective_config() -> Config:
    """Config fran .env, med sparade overrides ovanpa."""
    load_dotenv()
    try:
        cfg = load_config()
    except ConfigError:
        # Ingen nyckel i .env - lat installningssidan satta den i stallet.
        cfg = Config(api_key="")

    for field, value in settings_store.load_overrides().items():
        if value is None or not hasattr(cfg, field):
            continue
        setattr(cfg, field, value)
    return cfg


def public_settings(cfg: Config) -> dict:
    """Installningar for klienten - hemliga nycklar maskeras till booleans."""
    return {
        "base_url": cfg.base_url,
        "model": cfg.model,
        "system_prompt": cfg.system_prompt or "",
        "thinking": cfg.thinking,
        "search": cfg.search,
        "doc_search": cfg.doc_search,
        "rerank": cfg.rerank,
        "rerank_model": cfg.rerank_model,
        "rerank_candidates": cfg.rerank_candidates,
        "embed_model": cfg.embed_model,
        "rag_top_k": cfg.rag_top_k,
        "request_timeout": cfg.request_timeout,
        "has_api_key": bool(cfg.api_key),
        "has_brave_key": bool(cfg.brave_api_key),
        # Multi-leverantor
        "provider": cfg.provider,
        "active_model": cfg.active_llm().model,
        "berget_base_url": cfg.berget_base_url,
        "berget_model": cfg.berget_model,
        "berget_price_in": cfg.berget_price_in,
        "berget_price_out": cfg.berget_price_out,
        "anthropic_model": cfg.anthropic_model,
        "has_berget_key": bool(cfg.berget_api_key),
        "has_anthropic_key": bool(cfg.anthropic_api_key),
    }
