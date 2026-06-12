"""Starta webb-GUI:t (FastAPI-backend som aven serverar den byggda frontenden).

    python run_web.py            # startar pa http://localhost:8000
    python run_web.py --reload   # med auto-reload vid kodandringar

Bygg frontenden forst (engangsbruk eller efter andringar i web/):
    cd web && npm install && npm run build
"""
from __future__ import annotations

import argparse
import os
import sys

import uvicorn

ROOT = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    parser = argparse.ArgumentParser(description="Starta PocGrunden webb-GUI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="Auto-reload vid kodandring")
    args = parser.parse_args()

    if not os.path.isdir(os.path.join(ROOT, "web", "dist")):
        print("OBS: web/dist saknas - bygg frontenden forst:")
        print("    cd web && npm install && npm run build\n")

    print(f"Startar pa http://{args.host}:{args.port}")
    uvicorn.run("server.app:app", host=args.host, port=args.port, reload=args.reload, app_dir=ROOT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
