"""Utvardera RAG-retrieval mot ett testset med facit.

Mater for varje fraga om ratt sida och ratt nyckelord finns bland topp-K
traffar (recall@k). Ger en baslinje som kan jamforas mellan Steg 1 (dense)
och Steg 2 (hybrid).

Anvandning:
    python eval.py            # K = RAG_TOP_K (standard 5)
    python eval.py 10         # K = 10
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

import rag
from config import ConfigError, load_config

QUESTIONS = os.path.join("eval", "questions.jsonl")


def load_questions(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def page_hit(retrieved_pages: list[int], expected: list[int]) -> bool:
    return any(p in expected for p in retrieved_pages)


def keyword_hit(text: str, keywords: list[str]) -> bool:
    low = text.lower()
    return any(kw.lower() in low for kw in keywords)


def main(argv: list[str]) -> int:
    try:
        config = load_config()
    except ConfigError as err:
        print(f"Konfigurationsfel: {err}")
        return 1

    k = int(argv[0]) if argv else config.rag_top_k

    chunks, mat = rag.load_index(config)
    if not chunks or mat is None:
        print("Indexet ar tomt. Kor `python ingest.py` forst.")
        return 1

    items = load_questions(QUESTIONS)
    print(f"Utvarderar {len(items)} fragor mot {len(chunks)} chunks, K={k}\n")

    # Embedda alla fragor i ett svep (billigare an en i taget)
    qvecs = rag.embed_texts([it["q"] for it in items], config)

    by_cat: dict[str, list[tuple[bool, bool]]] = defaultdict(list)
    print(f"{'':2} {'sida':4} {'nyckel':6}  kategori    fraga")
    print("-" * 88)
    for it, qvec in zip(items, qvecs):
        results = rag.rank(qvec, chunks, mat, k)
        pages = [c.page for c, _ in results]
        text = "\n".join(c.text for c, _ in results)

        ph = page_hit(pages, it["pages"])
        kh = keyword_hit(text, it["keywords"])
        by_cat[it["category"]].append((ph, kh))

        mark = "OK" if (ph and kh) else ("~" if (ph or kh) else "X")
        print(
            f"{mark:2} {'JA ' if ph else 'nej':4} {'JA ' if kh else 'nej':6}  "
            f"{it['category']:10}  {it['q'][:46]}"
        )

    # Sammanfattning per kategori
    print("\n" + "=" * 60)
    print(f"{'Kategori':12} {'n':>3} {'sid-recall':>11} {'nyckel-recall':>14}")
    print("-" * 60)
    tot_p = tot_k = tot_n = 0
    for cat in sorted(by_cat):
        rows = by_cat[cat]
        n = len(rows)
        p = sum(1 for ph, _ in rows if ph)
        kk = sum(1 for _, kh in rows if kh)
        tot_p += p
        tot_k += kk
        tot_n += n
        print(f"{cat:12} {n:>3} {f'{p}/{n}':>11} {f'{kk}/{n}':>14}")
    print("-" * 60)
    print(
        f"{'TOTALT':12} {tot_n:>3} "
        f"{f'{tot_p}/{tot_n} ({100*tot_p//tot_n}%)':>11} "
        f"{f'{tot_k}/{tot_n} ({100*tot_k//tot_n}%)':>14}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
