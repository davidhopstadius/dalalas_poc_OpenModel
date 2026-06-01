"""Indexera PDF-dokument i det lokala RAG-indexet.

Anvandning:
    python ingest.py                     # indexerar allt i mappen documents/
    python ingest.py <pdf eller mapp>    # indexerar angiven fil/mapp

Korrs om nar som helst for att lagga till fler dokument (t.ex. vid demo):
lagg PDF:en i documents/ och kor `python ingest.py`. Varje dokument lagras
som ett eget filpar i rag_index/.
"""
from __future__ import annotations

import os
import sys

import fitz  # PyMuPDF

import rag
from config import ConfigError, load_config

DOCS_DIR = "documents"
MAX_CHARS = 1200
OVERLAP = 150


def chunk_text(text: str, max_chars: int = MAX_CHARS, overlap: int = OVERLAP) -> list[str]:
    """Dela text i bitar pa ca max_chars, med overlapp, brutet pa blankrad/mellanslag."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    pieces: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            # backa till radbrytning/mellanslag for renare snitt, men inte forbi mitten
            window_min = start + max_chars // 2
            cut = text.rfind("\n", window_min, end)
            if cut == -1:
                cut = text.rfind(" ", window_min, end)
            if cut != -1:
                end = cut
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= n:
            break
        start = max(end - overlap, start + 1)  # garanterar framsteg
    return pieces


def parse_pdf(path: str) -> list[rag.Chunk]:
    """Las en PDF sida for sida: tabeller som egna chunks + ovrig text."""
    doc_name = os.path.basename(path)
    chunks: list[rag.Chunk] = []
    with fitz.open(path) as pdf:
        for i, page in enumerate(pdf, start=1):
            # Tabeller forst - halls intakta sa rader inte tappar koppling
            try:
                tables = page.find_tables()
                for t in tables.tables:
                    md = t.to_markdown().strip()
                    if md:
                        chunks.append(
                            rag.Chunk(
                                text=f"Tabell (sida {i}):\n{md}",
                                doc=doc_name,
                                page=i,
                                type="table",
                            )
                        )
            except Exception:
                pass  # tabell-detektering kan fela pa vissa sidor; hoppa over

            text = page.get_text("text")
            for piece in chunk_text(text):
                chunks.append(rag.Chunk(text=piece, doc=doc_name, page=i, type="text"))
    return chunks


def expand_paths(args: list[str]) -> list[str]:
    """Expandera mappar till alla .pdf-filer i dem."""
    paths: list[str] = []
    for arg in args:
        if os.path.isdir(arg):
            for name in sorted(os.listdir(arg)):
                if name.lower().endswith(".pdf"):
                    paths.append(os.path.join(arg, name))
        elif os.path.isfile(arg):
            paths.append(arg)
        else:
            print(f"Hoppar over (hittas inte): {arg}")
    return paths


def main(argv: list[str]) -> int:
    try:
        config = load_config()
    except ConfigError as err:
        print(f"Konfigurationsfel: {err}")
        return 1

    # Utan argument: indexera allt i documents/
    if not argv:
        if not os.path.isdir(DOCS_DIR):
            print(f"Mappen '{DOCS_DIR}/' saknas. Lagg dina PDF:er dar och kor igen,")
            print("eller ange en fil/mapp: python ingest.py <pdf eller mapp>")
            return 1
        argv = [DOCS_DIR]

    paths = expand_paths(argv)
    if not paths:
        print(f"Inga PDF-filer att indexera i: {', '.join(argv)}")
        return 1

    for path in paths:
        doc_name = os.path.basename(path)
        print(f"Laser {doc_name} ...")
        chunks = parse_pdf(path)
        if not chunks:
            print(f"  (inga textchunks hittades, hoppar over)")
            continue
        print(f"  {len(chunks)} chunks. Embeddar via {config.embed_model} ...")
        embeddings = rag.embed_texts([c.text for c in chunks], config)
        base = rag.save_doc(config, doc_name, chunks, embeddings)
        print(f"  Sparat: {base}.jsonl / .npy")

    print(f"\nKlart. Indexerade dokument: {', '.join(rag.indexed_docs(config))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
