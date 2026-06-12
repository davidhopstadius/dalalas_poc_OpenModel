"""Utvardera RAG-retrieval mot ett testset med facit.

Mater for varje fraga om ratt sida och ratt nyckelord finns bland topp-K
traffar (recall@k). Varje korning SPARAS till eval/results/<label>.json sa
att resultat kan jamforas mellan Steg 1 (dense) och Steg 2 (hybrid).

Anvandning:
    python eval.py                         # K=5, sparas som "latest"
    python eval.py --k 10 --label steg1    # spara baslinje som steg1
    python eval.py --label steg2 --compare steg1   # kor + visa skillnad mot steg1
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timezone

import rag
from config import ConfigError, load_config

QUESTIONS = os.path.join("eval", "questions.jsonl")
RESULTS_DIR = os.path.join("eval", "results")


def load_questions(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def page_hit(retrieved_pages: list[int], expected: list[int]) -> bool:
    return any(p in expected for p in retrieved_pages)


def keyword_hit(text: str, keywords: list[str]) -> bool:
    low = text.lower()
    return any(kw.lower() in low for kw in keywords)


def summarize(per_question: list[dict]) -> tuple[dict, dict]:
    """Returnera (by_category, total) med antal sid-/nyckeltraffar."""
    by_cat: dict[str, dict] = defaultdict(lambda: {"n": 0, "page": 0, "keyword": 0})
    total = {"n": 0, "page": 0, "keyword": 0}
    for r in per_question:
        for bucket in (by_cat[r["category"]], total):
            bucket["n"] += 1
            bucket["page"] += int(r["page_hit"])
            bucket["keyword"] += int(r["keyword_hit"])
    return dict(by_cat), total


def run_eval(config, k: int) -> dict:
    chunks, mat = rag.load_index(config)
    if not chunks or mat is None:
        raise SystemExit("Indexet ar tomt. Kor `python ingest.py` forst.")

    items = load_questions(QUESTIONS)
    qvecs = rag.embed_texts([it["q"] for it in items], config)

    per_question = []
    for it, qvec in zip(items, qvecs):
        results = rag.search(it["q"], qvec, chunks, mat, config, k)
        pages = [c.page for c, _ in results]
        text = "\n".join(c.text for c, _ in results)
        per_question.append(
            {
                "q": it["q"],
                "category": it["category"],
                "page_hit": page_hit(pages, it["pages"]),
                "keyword_hit": keyword_hit(text, it["keywords"]),
            }
        )

    by_cat, total = summarize(per_question)
    return {
        "label": None,
        "k": k,
        "rerank": config.rerank,
        "chunks": len(chunks),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "per_question": per_question,
        "by_category": by_cat,
        "total": total,
    }


def print_report(res: dict) -> None:
    rr = "pa" if res.get("rerank") else "av"
    print(
        f"Utvarderade {res['total']['n']} fragor mot {res['chunks']} chunks, "
        f"K={res['k']}, rerank={rr}\n"
    )
    print(f"{'':2} {'sida':4} {'nyckel':6}  kategori    fraga")
    print("-" * 88)
    for r in res["per_question"]:
        ph, kh = r["page_hit"], r["keyword_hit"]
        mark = "OK" if (ph and kh) else ("~" if (ph or kh) else "X")
        print(
            f"{mark:2} {'JA ' if ph else 'nej':4} {'JA ' if kh else 'nej':6}  "
            f"{r['category']:10}  {r['q'][:46]}"
        )

    print("\n" + "=" * 60)
    print(f"{'Kategori':12} {'n':>3} {'sid-recall':>11} {'nyckel-recall':>14}")
    print("-" * 60)
    for cat in sorted(res["by_category"]):
        c = res["by_category"][cat]
        page_cell = f"{c['page']}/{c['n']}"
        kw_cell = f"{c['keyword']}/{c['n']}"
        print(f"{cat:12} {c['n']:>3} {page_cell:>11} {kw_cell:>14}")
    print("-" * 60)
    t = res["total"]
    page_cell = f"{t['page']}/{t['n']} ({100 * t['page'] // t['n']}%)"
    kw_cell = f"{t['keyword']}/{t['n']} ({100 * t['keyword'] // t['n']}%)"
    print(f"{'TOTALT':12} {t['n']:>3} {page_cell:>11} {kw_cell:>14}")


def print_compare(curr: dict, base: dict) -> None:
    print("\n" + "#" * 60)
    print(f"SKILLNAD mot '{base['label']}' (K={base['k']})")
    print("-" * 60)

    def pct(b):
        return 100 * b["page"] // b["n"], 100 * b["keyword"] // b["n"]

    cp, ck = pct(curr["total"])
    bp, bk = pct(base["total"])
    print(f"  sid-recall   : {bp}%  ->  {cp}%  ({cp - bp:+d} pe)")
    print(f"  nyckel-recall: {bk}%  ->  {ck}%  ({ck - bk:+d} pe)")

    # Vilka fragor andrade status?
    base_q = {r["q"]: r for r in base["per_question"]}
    changes = []
    for r in curr["per_question"]:
        b = base_q.get(r["q"])
        if b and (r["page_hit"], r["keyword_hit"]) != (b["page_hit"], b["keyword_hit"]):
            changes.append((r, b))
    if changes:
        print("\n  Andrade fragor (sida/nyckel):")
        for r, b in changes:
            def s(x):
                return f"{'J' if x['page_hit'] else 'n'}{'J' if x['keyword_hit'] else 'n'}"
            print(f"    {s(b)} -> {s(r)}  {r['q'][:50]}")
    else:
        print("\n  (inga fragor bytte status)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Utvardera RAG-retrieval.")
    parser.add_argument("--k", type=int, default=None, help="Antal traffar (default RAG_TOP_K)")
    parser.add_argument("--label", default="latest", help="Namn pa sparad resultatfil")
    parser.add_argument("--compare", default=None, help="Label pa tidigare korning att jamfora mot")
    parser.add_argument(
        "--rerank", dest="rerank", action="store_true", default=None,
        help="Tvinga reranking pa (Steg 2)",
    )
    parser.add_argument(
        "--no-rerank", dest="rerank", action="store_false",
        help="Tvinga reranking av (ren dense, Steg 1)",
    )
    args = parser.parse_args()

    try:
        config = load_config()
    except ConfigError as err:
        print(f"Konfigurationsfel: {err}")
        return 1

    if args.rerank is not None:
        config.rerank = args.rerank
    k = args.k or config.rag_top_k
    res = run_eval(config, k)
    res["label"] = args.label
    print_report(res)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, f"{args.label}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(f"\nSparat: {path}")

    if args.compare:
        base_path = os.path.join(RESULTS_DIR, f"{args.compare}.json")
        if not os.path.exists(base_path):
            print(f"\nHittar ingen tidigare korning: {base_path}")
        else:
            with open(base_path, encoding="utf-8") as f:
                print_compare(res, json.load(f))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
