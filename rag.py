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
import sys
from dataclasses import asdict, dataclass

import httpx
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


# Lat-initierad lokal embeddings-modell (fastembed/ONNX, CPU). Laddas en gang
# och ateranvands - forsta anropet laddar ner modellen (~2 GB) till cache.
_local_embedder = None
_local_embedder_name: str | None = None


def _local_embed(texts: list[str], config: Config, is_query: bool) -> np.ndarray:
    """Embed lokalt via fastembed. e5-modeller kraver query/passage-prefix -
    fastembeds query_embed/passage_embed satter ratt prefix per modell."""
    global _local_embedder, _local_embedder_name
    if _local_embedder is None or _local_embedder_name != config.local_embed_model:
        from fastembed import TextEmbedding  # tung import - bara nar lokal backend anvands

        _local_embedder = TextEmbedding(model_name=config.local_embed_model)
        _local_embedder_name = config.local_embed_model
    gen = _local_embedder.query_embed(texts) if is_query else _local_embedder.passage_embed(texts)
    return np.array(list(gen), dtype=np.float32)


# Lat-initierad lokal reranker (fastembed cross-encoder, CPU). Som embeddern:
# laddas en gang, forsta anropet laddar ner modellen (~1 GB) till cache.
_local_reranker = None
_local_reranker_name: str | None = None


def _local_rerank(query: str, texts: list[str], config: Config) -> list[tuple[int, float]]:
    """Rerank lokalt via fastembeds cross-encoder. Returnerar (index, score)
    sorterat med hogst score forst - samma kontrakt som Grunden-vagen."""
    global _local_reranker, _local_reranker_name
    if _local_reranker is None or _local_reranker_name != config.local_rerank_model:
        from fastembed.rerank.cross_encoder import TextCrossEncoder  # tung import - bara vid lokal rerank

        _local_reranker = TextCrossEncoder(model_name=config.local_rerank_model)
        _local_reranker_name = config.local_rerank_model
    scores = list(_local_reranker.rerank(query, texts))  # en score per text, i indata-ordning
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    return [(i, float(s)) for i, s in ranked]


def _safe_name(doc: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", doc)


def embed_texts(texts: list[str], config: Config, is_query: bool = False) -> np.ndarray:
    """Embed en lista texter. Backend valjs av config.embed_backend.

    is_query skiljer fragor fran dokument - kravs av e5-modeller (lokal backend)
    och ignoreras av Grundens bge-m3.
    """
    if config.embed_backend == "local":
        return _local_embed(texts, config, is_query)

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


def rank(query_vec: np.ndarray, chunks: list[Chunk], mat: np.ndarray, k: int) -> list[tuple[Chunk, float]]:
    """Rangordna chunks mot en redan embeddad fraga (cosine-likhet)."""
    q = query_vec / (np.linalg.norm(query_vec) + 1e-9)
    norms = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)
    sims = norms @ q
    top = np.argsort(-sims)[:k]
    return [(chunks[i], float(sims[i])) for i in top]


def rerank_scores(query: str, texts: list[str], config: Config) -> list[tuple[int, float]]:
    """Rerank-poang fran Grundens cross-encoder (BGE-reranker).

    Returnerar (index_i_texts, score) sorterat med hogst score forst. Vid fel
    (t.ex. endpoint nere under en demo) kastas httpx.HTTPError - anroparen
    faller da tillbaka pa dense-ordningen.
    """
    if not texts:
        return []
    if config.rerank_backend == "local":
        return _local_rerank(query, texts, config)

    resp = httpx.post(
        config.base_url.rstrip("/") + "/rerank",
        headers={"Authorization": f"Bearer {config.api_key}"},
        json={"model": config.rerank_model, "query": query, "texts": texts},
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return [(item["index"], float(item["score"])) for item in data]


def search(
    query: str,
    query_vec: np.ndarray,
    chunks: list[Chunk],
    mat: np.ndarray,
    config: Config,
    k: int | None = None,
) -> list[tuple[Chunk, float]]:
    """Hamta de k basta chunkarna for en redan embeddad fraga.

    Steg 1 (config.rerank=False): ren dense-sokning (cosine).
    Steg 2 (config.rerank=True): hamta rerank_candidates dense-traffar och lat
    BGE-rerankern omsortera dem. Samma flagga styr CLI (/rerank) och GUI:t, och
    den lases vid varje fraga sa den kan slas av/pa live i ett kundmote.
    """
    k = k or config.rag_top_k
    if not config.rerank:
        return rank(query_vec, chunks, mat, k)

    pool = max(config.rerank_candidates, k)
    dense = rank(query_vec, chunks, mat, pool)
    try:
        order = rerank_scores(query, [c.text for c, _ in dense], config)
    except Exception as err:
        # Grundens rerank nere (424/502) eller lokal modell som inte gick att
        # ladda -> falla tillbaka pa dense-ordningen sa fragan aldrig kraschar.
        print(f"  [rerank misslyckades, anvander dense: {err}]", file=sys.stderr)
        return dense[:k]
    return [(dense[i][0], score) for i, score in order][:k]


def retrieve(query: str, config: Config, k: int | None = None) -> list[tuple[Chunk, float]]:
    """Hamta de k mest relevanta chunkarna for fragan (dense, ev. + rerank)."""
    k = k or config.rag_top_k
    chunks, mat = load_index(config)
    if not chunks or mat is None:
        return []
    query_vec = embed_texts([query], config, is_query=True)[0]
    return search(query, query_vec, chunks, mat, config, k)


def format_results(results: list[tuple[Chunk, float]]) -> str:
    """Formatera traffarna som text at modellen, med kallhanvisning."""
    if not results:
        return "Inga traffar i dokumentindexet."
    blocks = []
    for chunk, _score in results:
        blocks.append(f"[Kalla: {chunk.doc}, sida {chunk.page}]\n{chunk.text}")
    return "\n\n---\n\n".join(blocks)
