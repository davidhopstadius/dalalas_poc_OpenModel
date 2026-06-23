"""Prismodell per leverantor och modell.

Priser anges per 1 miljon tokens i leverantorens valuta:
- Grunden.ai (SEK): https://grunden.ai/modeller  (glm-5.1 60/180)
- Anthropic (USD):  https://www.anthropic.com/pricing
- Berget AI (SEK):  prislistan ligger bakom inloggning -> tas fran Config
  (berget_price_in/out), som anvandaren fyller i under Installningar.

Embeddings (bge-m3) och reranker (bge-reranker-v2-m3) ar kostnadsfria hos Grunden
och anvands dessutom lokalt -> ingen kostnad har.
"""
from __future__ import annotations

# provider -> model -> {"input", "output", "currency"} (per 1M tokens)
PRICING: dict = {
    "grunden": {
        "glm-5.1": {"input": 60.0, "output": 180.0, "currency": "SEK"},
    },
    "anthropic": {
        "claude-opus-4-8": {"input": 5.0, "output": 25.0, "currency": "USD"},
        "claude-sonnet-4-6": {"input": 3.0, "output": 15.0, "currency": "USD"},
        "claude-haiku-4-5": {"input": 1.0, "output": 5.0, "currency": "USD"},
    },
    # berget hanteras dynamiskt via Config (se rates()).
}

# Faller tillbaka pa Grundens glm-5.1-takt om en okand modell anvands.
_DEFAULT = {"input": 60.0, "output": 180.0, "currency": "SEK"}


def rates(provider: str, model: str, cfg=None) -> dict:
    """Takt (in/out per 1M + valuta) for en given leverantor+modell.

    Berget saknar publik prislista -> tas fran Config (berget_price_in/out, SEK).
    """
    if provider == "berget":
        return {
            "input": float(getattr(cfg, "berget_price_in", 0.0) or 0.0),
            "output": float(getattr(cfg, "berget_price_out", 0.0) or 0.0),
            "currency": "SEK",
        }
    return PRICING.get(provider, {}).get(model, _DEFAULT)


def cost(provider: str, model: str, prompt_tokens: int, completion_tokens: int, cfg=None) -> tuple[float, str]:
    """Kostnad for ett antal in-/ut-tokens. Returnerar (belopp, valuta)."""
    r = rates(provider, model, cfg)
    amount = (
        prompt_tokens / 1_000_000 * float(r["input"])
        + completion_tokens / 1_000_000 * float(r["output"])
    )
    return amount, str(r["currency"])
