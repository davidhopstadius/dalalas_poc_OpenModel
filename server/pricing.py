"""Prismodell for nuvarande AI-leverantor (Grunden.ai).

Priser i SEK per 1 miljon tokens. Kalla: https://grunden.ai/modeller
(standardtakt; priserna anges in/ut). Embeddings (bge-m3) och reranker
(bge-reranker-v2-m3) ar i skrivande stund kostnadsfria hos Grunden.

Uppdatera tabellen nedan om Grunden andrar sin prislista eller om en annan
modell tas i bruk.
"""
from __future__ import annotations

CURRENCY = "SEK"

# model -> {"input": kr per 1M in-tokens, "output": kr per 1M ut-tokens}
PRICING: dict[str, dict[str, float]] = {
    "glm-5.1": {"input": 60.0, "output": 180.0},
}

# Faller tillbaka pa glm-5.1:s takt om en okand modell anvands.
_DEFAULT = {"input": 60.0, "output": 180.0}


def rates(model: str) -> dict[str, float]:
    return PRICING.get(model, _DEFAULT)


def cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Kostnad i SEK for ett givet antal in-/ut-tokens."""
    r = rates(model)
    return (
        prompt_tokens / 1_000_000 * r["input"]
        + completion_tokens / 1_000_000 * r["output"]
    )
