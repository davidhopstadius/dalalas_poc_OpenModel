"""FastAPI-app: chatt (SSE), konversationer, dokument (RAG) och installningar."""
from __future__ import annotations

import json
import os
import queue
import re
import threading
import time

# Forankra processen i projektroten sa de relativa sokvagarna (rag_index/,
# documents/, .env, data/) fungerar oavsett varifran servern startas.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_PROJECT_ROOT)

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import ingest
import rag
from chat import build_chat
from openai import OpenAIError
from server import pricing, runtime, settings_store, store

app = FastAPI(title="PocGrunden GUI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # lokal app
    allow_methods=["*"],
    allow_headers=["*"],
)

CITATION_RE = re.compile(r"\[Kalla: (.+?), sida (\d+)\]")

store.init_db()


def _warm_up_local_models() -> None:
    """Pre-ladda de lokala RAG-modellerna (e5 + reranker) i en bakgrundstrad.

    Forsta doc_search efter processtart laddar annars modellerna lat (~3 GB ->
    RAM/nedladdning), vilket ger en flerminuters-spik pa den forsta fragan. Genom
    att varma upp vid start ar de redan i RAM nar anvandaren staller sin fraga.
    """
    import sys

    import rag

    try:
        cfg = runtime.effective_config()
    except Exception:  # noqa: BLE001
        return
    if cfg.embed_backend == "local":
        try:
            rag.embed_texts(["uppvarmning"], cfg, is_query=True)
        except Exception as err:  # noqa: BLE001 - warm-up far aldrig falla servern
            print(f"[warmup] embeddings: {err}", file=sys.stderr)
    if cfg.rerank and cfg.rerank_backend == "local":
        try:
            rag._local_rerank("uppvarmning", ["uppvarmning"], cfg)
        except Exception as err:  # noqa: BLE001
            print(f"[warmup] reranker: {err}", file=sys.stderr)
    print("[warmup] lokala RAG-modeller klara", file=sys.stderr)


threading.Thread(target=_warm_up_local_models, daemon=True).start()


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _query_of(arguments: str) -> str:
    try:
        return json.loads(arguments).get("query", "") if arguments else ""
    except json.JSONDecodeError:
        return ""


# --------------------------------------------------------------------------- #
#  Chatt (SSE-streaming)
# --------------------------------------------------------------------------- #
class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


@app.post("/api/chat")
def chat(req: ChatRequest):
    cfg = runtime.effective_config()
    # Validera den AKTIVA leverantorens nyckel (inte alltid Grundens), sa ett
    # saknat Berget-/Anthropic-varde ger ett tydligt fel i stallet for ett raare
    # SDK-autentiseringsfel langre in.
    if not cfg.active_llm().api_key:
        raise HTTPException(
            400,
            f"Ingen API-nyckel konfigurerad for vald leverantor ({cfg.provider}). "
            "Satt den under Installningar.",
        )

    message = req.message.strip()
    if not message:
        raise HTTPException(400, "Tomt meddelande.")

    if req.conversation_id and store.conversation_exists(req.conversation_id):
        conv_id = req.conversation_id
    else:
        # Lagra vilken leverantor/modell som STARTADE samtalet (visas i sidopanelens
        # tooltip aven om man byter leverantor senare).
        conv_id = store.create_conversation(
            title=message, model=cfg.active_llm().model, provider=cfg.provider
        )

    prior = store.get_messages(conv_id)
    bot = build_chat(cfg)
    # Seeda historiken med tidigare turer (leverantorsspecifikt - se chat.py).
    bot.seed_history(prior)
    store.add_message(conv_id, "user", message)

    def event_stream():
        q: queue.Queue = queue.Queue()
        citations: list[dict] = []

        def on_token(text: str) -> None:
            q.put(("token", text))

        def on_tool(name: str, arguments: str) -> None:
            q.put(("tool", name, _query_of(arguments)))

        def on_tool_result(name: str, result: str) -> None:
            if name == "doc_search":
                for doc, page in CITATION_RE.findall(result):
                    cite = {"doc": doc, "page": int(page)}
                    if cite not in citations:
                        citations.append(cite)

        def worker():
            try:
                t0 = time.perf_counter()
                answer = bot.ask(
                    message,
                    on_tool=on_tool,
                    on_token=on_token,
                    on_tool_result=on_tool_result,
                )
                latency_ms = int((time.perf_counter() - t0) * 1000)
                q.put(("final", answer, latency_ms))
            except OpenAIError as err:
                q.put(("error", str(err)))
            except Exception as err:  # noqa: BLE001 - vill aldrig hanga strommen
                q.put(("error", f"Ovantat fel: {err}"))

        threading.Thread(target=worker, daemon=True).start()

        yield _sse({"type": "start", "conversation_id": conv_id})
        while True:
            item = q.get()
            kind = item[0]
            if kind == "token":
                yield _sse({"type": "token", "text": item[1]})
            elif kind == "tool":
                yield _sse({"type": "tool", "name": item[1], "query": item[2]})
            elif kind == "final":
                msg_id = store.add_message(conv_id, "assistant", item[1], citations)
                store.record_usage(
                    conv_id,
                    msg_id,
                    bot.model,
                    bot.usage["prompt_tokens"],
                    bot.usage["completion_tokens"],
                    provider=cfg.provider,
                    latency_ms=item[2],
                )
                yield _sse(
                    {
                        "type": "done",
                        "conversation_id": conv_id,
                        "message_id": msg_id,
                        "citations": citations,
                    }
                )
                break
            elif kind == "error":
                yield _sse({"type": "error", "message": item[1]})
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# --------------------------------------------------------------------------- #
#  Konversationer
# --------------------------------------------------------------------------- #
class RenameRequest(BaseModel):
    title: str


@app.get("/api/conversations")
def list_conversations():
    return store.list_conversations()


@app.get("/api/conversations/{conv_id}")
def get_conversation(conv_id: str):
    if not store.conversation_exists(conv_id):
        raise HTTPException(404, "Samtalet finns inte.")
    return {"id": conv_id, "messages": store.get_messages(conv_id)}


@app.patch("/api/conversations/{conv_id}")
def rename_conversation(conv_id: str, req: RenameRequest):
    if not store.conversation_exists(conv_id):
        raise HTTPException(404, "Samtalet finns inte.")
    store.rename_conversation(conv_id, req.title)
    return {"ok": True}


@app.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: str):
    store.delete_conversation(conv_id)
    return {"ok": True}


# --------------------------------------------------------------------------- #
#  Dokument (RAG)
# --------------------------------------------------------------------------- #
def _doc_summaries(cfg) -> list[dict]:
    import glob

    out = []
    for jl in sorted(glob.glob(os.path.join(cfg.index_dir, "*.jsonl"))):
        try:
            with open(jl, encoding="utf-8") as f:
                lines = [ln for ln in f if ln.strip()]
            name = json.loads(lines[0])["doc"] if lines else os.path.basename(jl)
            pages = {json.loads(ln)["page"] for ln in lines}
            out.append({"doc": name, "chunks": len(lines), "pages": len(pages)})
        except (OSError, json.JSONDecodeError, KeyError, IndexError):
            continue
    return out


@app.get("/api/documents")
def list_documents():
    cfg = runtime.effective_config()
    return {"documents": _doc_summaries(cfg), "doc_search": cfg.doc_search}


@app.post("/api/documents")
async def upload_document(file: UploadFile):
    cfg = runtime.effective_config()
    if not cfg.api_key:
        raise HTTPException(400, "Ingen API-nyckel konfigurerad - kan inte embedda.")
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Endast PDF stods just nu.")

    os.makedirs(ingest.DOCS_DIR, exist_ok=True)
    dest = os.path.join(ingest.DOCS_DIR, os.path.basename(file.filename))
    with open(dest, "wb") as f:
        f.write(await file.read())

    try:
        chunks = ingest.parse_pdf(dest)
        if not chunks:
            raise HTTPException(422, "Hittade ingen text i PDF:en.")
        embeddings = rag.embed_texts([c.text for c in chunks], cfg)
        rag.save_doc(cfg, os.path.basename(dest), chunks, embeddings)
    except OpenAIError as err:
        raise HTTPException(503, f"Embeddings-tjansten svarar inte just nu: {err}")

    return {"doc": os.path.basename(dest), "chunks": len(chunks)}


@app.delete("/api/documents/{doc_name}")
def delete_document(doc_name: str):
    cfg = runtime.effective_config()
    base = os.path.join(cfg.index_dir, rag._safe_name(doc_name))
    removed = False
    for ext in (".jsonl", ".npy"):
        path = base + ext
        if os.path.exists(path):
            os.remove(path)
            removed = True
    src = os.path.join(ingest.DOCS_DIR, doc_name)
    if os.path.exists(src):
        os.remove(src)
    if not removed:
        raise HTTPException(404, "Dokumentet finns inte i indexet.")
    return {"ok": True}


# --------------------------------------------------------------------------- #
#  Driftinfo (token-anvandning och kostnad)
# --------------------------------------------------------------------------- #
@app.get("/api/usage")
def get_usage():
    cfg = runtime.effective_config()
    # Visa enbart statistik for den aktiva leverantoren.
    summary = store.usage_summary(cfg.provider)

    # Summera kostnaden per valuta (Grunden/Berget i SEK, Anthropic i USD) sa vi
    # aldrig blandar ihop valutor i en och samma siffra.
    for key in ("last_message", "last_conversation", "today", "total"):
        block = summary[key]
        costs: dict[str, float] = {}
        for grp in block.get("by_model", []):
            amount, currency = pricing.cost(
                grp["provider"], grp["model"],
                grp["prompt_tokens"], grp["completion_tokens"], cfg,
            )
            costs[currency] = round(costs.get(currency, 0.0) + amount, 4)
        block["costs"] = costs

    active = cfg.active_llm()
    r = pricing.rates(cfg.provider, active.model, cfg)
    summary["provider"] = cfg.provider
    summary["model"] = active.model
    summary["rates"] = {
        "input_per_mtok": r["input"],
        "output_per_mtok": r["output"],
        "currency": r["currency"],
    }
    return summary


@app.delete("/api/usage")
def reset_usage():
    """Nollstall all token-/kostnadsstatistik (alla leverantorer). Samtalen lamnas."""
    store.reset_usage()
    return {"ok": True}


# --------------------------------------------------------------------------- #
#  Installningar
# --------------------------------------------------------------------------- #
class SettingsUpdate(BaseModel):
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    brave_api_key: str | None = None
    system_prompt: str | None = None
    thinking: bool | None = None
    search: bool | None = None
    doc_search: bool | None = None
    rerank: bool | None = None
    rerank_model: str | None = None
    rerank_candidates: int | None = None
    embed_model: str | None = None
    rag_top_k: int | None = None
    request_timeout: float | None = None
    # Multi-leverantor
    provider: str | None = None
    berget_base_url: str | None = None
    berget_model: str | None = None
    berget_api_key: str | None = None
    berget_price_in: float | None = None
    berget_price_out: float | None = None
    anthropic_model: str | None = None
    anthropic_api_key: str | None = None


@app.get("/api/settings")
def get_settings():
    return runtime.public_settings(runtime.effective_config())


@app.put("/api/settings")
def update_settings(req: SettingsUpdate):
    settings_store.save_overrides(req.model_dump(exclude_unset=True))
    return runtime.public_settings(runtime.effective_config())


# --------------------------------------------------------------------------- #
#  Statisk frontend (om web/dist ar byggd)
# --------------------------------------------------------------------------- #
_DIST = os.path.join(os.path.dirname(__file__), "..", "web", "dist")
if os.path.isdir(_DIST):
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="web")
