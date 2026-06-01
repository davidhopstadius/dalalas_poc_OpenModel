"""Lokalt RAG-index for dokumentsokning.

Lagring: ett par filer per dokument i `index_dir`:
  <doc>.jsonl  - en chunk per rad (text + metadata)
  <doc>.npy    - matris med embeddings (samma ordning som raderna)

Det gor det enkelt att lagga till fler dokument vid demotillfallet: kor
`ingest.py <pdf>` igen, sa skrivs ett nytt par filer. Sokningen laddar och
slar ihop alla par.
"""
from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import asdict, dataclass

import numpy as np
from openai import OpenAI

from config import Config

EMBED_BATCH = 32  # Grundens max batch-storlek for embeddings


@dataclass
class Chunk:
    text: str
    doc: str
    page: int
    type: str = "text"


def _client(config: Config) -> OpenAI:
    return OpenAI(api_key=config.api_key, base_url=config.base_url)


def _safe_name(doc: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", doc)


def embed_texts(texts: list[str], config: Config) -> np.ndarray:
    """Embed en lista texter via Grunden (bge-m3). Batchar anropen."""
    client = _client(config)
    vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i : i + EMBED_BATCH]
        resp = client.embeddings.create(model=config.embed_model, input=batch)
        vectors.extend(item.embedding for item in resp.data)
    return np.array(vectors, dtype=np.float32)


def save_doc(config: Config, doc_name: str, chunks: list[Chunk], embeddings: np.ndarray) -> str:
    """Spara ett dokuments chunks + embeddings som ett filpar i index_dir."""
    os.makedirs(config.index_dir, exist_ok=True)
    base = os.path.join(config.index_dir, _safe_name(doc_name))
    with open(base + ".jsonl", "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")
    np.save(base + ".npy", embeddings)
    return base


def has_index(config: Config) -> bool:
    """True om minst ett indexerat dokument finns."""
    return bool(glob.glob(os.path.join(config.index_dir, "*.jsonl")))


def indexed_docs(config: Config) -> list[str]:
    docs = []
    for jl in glob.glob(os.path.join(config.index_dir, "*.jsonl")):
        with open(jl, encoding="utf-8") as f:
            first = f.readline()
        if first:
            docs.append(json.loads(first)["doc"])
    return docs


def load_index(config: Config) -> tuple[list[Chunk], np.ndarray | None]:
    """Ladda och sla ihop alla indexerade dokument."""
    chunks: list[Chunk] = []
    mats: list[np.ndarray] = []
    for jl in sorted(glob.glob(os.path.join(config.index_dir, "*.jsonl"))):
        npy = jl[:-6] + ".npy"
        if not os.path.exists(npy):
            continue
        arr = np.load(npy)
        with open(jl, encoding="utf-8") as f:
            rows = [Chunk(**json.loads(line)) for line in f if line.strip()]
        # Skydda mot otakt mellan rader och vektorer
        n = min(len(rows), len(arr))
        chunks.extend(rows[:n])
        mats.append(arr[:n])
    if not chunks:
        return [], None
    return chunks, np.vstack(mats)


def retrieve(query: str, config: Config, k: int | None = None) -> list[tuple[Chunk, float]]:
    """Hamta de k mest relevanta chunkarna for fragan (cosine-likhet)."""
    k = k or config.rag_top_k
    chunks, mat = load_index(config)
    if not chunks or mat is None:
        return []
    q = embed_texts([query], config)[0]
    q = q / (np.linalg.norm(q) + 1e-9)
    norms = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)
    sims = norms @ q
    top = np.argsort(-sims)[:k]
    return [(chunks[i], float(sims[i])) for i in top]


def format_results(results: list[tuple[Chunk, float]]) -> str:
    """Formatera traffarna som text at modellen, med kallhanvisning."""
    if not results:
        return "Inga traffar i dokumentindexet."
    blocks = []
    for chunk, _score in results:
        blocks.append(f"[Kalla: {chunk.doc}, sida {chunk.page}]\n{chunk.text}")
    return "\n\n---\n\n".join(blocks)
