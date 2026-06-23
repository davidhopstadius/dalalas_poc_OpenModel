"""Redigerbara runtime-installningar, sparade i en lokal JSON-fil.

Overrides laggs ovanpa det som lases fran .env, sa anvandaren kan andra modell,
thinking, rerank m.m. - och peka om base_url/nyckel till en annan
OpenAI-kompatibel leverantor - direkt fran GUI:t utan att rora .env.
"""
from __future__ import annotations

import json
import os
from threading import Lock

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "settings.json")

# Falt som GUI:t far andra (matchar attribut pa config.Config).
ALLOWED_FIELDS = {
    "base_url",
    "model",
    "api_key",
    "brave_api_key",
    "system_prompt",
    "thinking",
    "search",
    "doc_search",
    "rerank",
    "rerank_model",
    "rerank_candidates",
    "embed_model",
    "rag_top_k",
    "request_timeout",
    # Multi-leverantor
    "provider",
    "berget_base_url",
    "berget_model",
    "berget_api_key",
    "berget_price_in",
    "berget_price_out",
    "anthropic_model",
    "anthropic_api_key",
}

# Falt som ar hemliga - returneras aldrig i klartext till klienten.
SECRET_FIELDS = {"api_key", "brave_api_key", "berget_api_key", "anthropic_api_key"}

_lock = Lock()


def _ensure_dir() -> None:
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)


def load_overrides() -> dict:
    """Las sparade overrides (tom dict om filen saknas)."""
    if not os.path.exists(SETTINGS_PATH):
        return {}
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if k in ALLOWED_FIELDS}
    except (json.JSONDecodeError, OSError):
        return {}


def save_overrides(updates: dict) -> dict:
    """Slå ihop nya varden med befintliga och spara. Returnerar nya overrides.

    Tomma hemliga falt ignoreras (sa man inte rakar nolla en nyckel av misstag).
    """
    with _lock:
        current = load_overrides()
        for key, value in updates.items():
            if key not in ALLOWED_FIELDS:
                continue
            if key in SECRET_FIELDS and (value is None or value == ""):
                continue  # ror inte en redan satt nyckel
            if value is None:
                current.pop(key, None)
            else:
                current[key] = value
        _ensure_dir()
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        return current
