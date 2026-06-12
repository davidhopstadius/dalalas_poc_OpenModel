"""FastAPI-backend for PocGrunden:s webb-GUI.

Tunn server som ateranvander den befintliga karnan (chat, rag, tools, config,
ingest). Exponerar chatt (SSE-streaming), konversationer (SQLite),
dokumentuppladdning (RAG) och redigerbara installningar.
"""
