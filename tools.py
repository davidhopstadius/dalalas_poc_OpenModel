"""Function-calling-verktyg som modellen kan anropa.

Verktyg:
  - web_search: sok pa webben via Brave Search API.
  - doc_search: sok i indexerad teknisk dokumentation (lokalt RAG-index).

Modellen ber om ett verktyg (tool_call), vi utfor det har och matar tillbaka
resultatet.
"""
from __future__ import annotations

import json

import httpx

import rag

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

# Schema som skickas till modellen i `tools`-faltet (OpenAI-format).
WEB_SEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Sok pa webben efter aktuell information. Anvand for fragor om "
            "nyheter, datum, fakta som kan ha andrats, eller nar du ar osaker."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Sokfras, formulerad for en sokmotor.",
                },
            },
            "required": ["query"],
        },
    },
}


DOC_SEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "doc_search",
        "description": (
            "Sok i den indexerade tekniska dokumentationen (installations- och "
            "servicemanualer for las-/dorrsystem). Anvand for fragor om specifika "
            "system, felsokning, felkoder, installation, kopplingar, installningar "
            "och artikelnummer. Citera alltid sida ur kallan i svaret."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Sokfras som beskriver vad teknikern vill veta.",
                },
            },
            "required": ["query"],
        },
    },
}


def web_search(query: str, api_key: str, count: int = 5) -> str:
    """Kor en Brave-sokning och returnerar resultaten som text at modellen."""
    resp = httpx.get(
        BRAVE_ENDPOINT,
        params={"q": query, "count": count},
        headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
        timeout=15.0,
    )
    resp.raise_for_status()
    results = resp.json().get("web", {}).get("results", [])
    if not results:
        return f"Inga sokresultat for: {query}"

    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "").strip()
        url = r.get("url", "").strip()
        desc = r.get("description", "").strip()
        lines.append(f"{i}. {title}\n   {url}\n   {desc}")
    return f"Sokresultat for '{query}':\n\n" + "\n\n".join(lines)


def schemas(config) -> list[dict] | None:
    """Returnera tools-schemat (verktygen som ar aktiverade), eller None."""
    tools: list[dict] = []
    if config.search_enabled:
        tools.append(WEB_SEARCH_SCHEMA)
    if config.doc_search and rag.has_index(config):
        tools.append(DOC_SEARCH_SCHEMA)
    return tools or None


def run_tool(name: str, arguments: str, config) -> str:
    """Kor verktyget som modellen begart och returnera resultatet som text."""
    try:
        args = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError:
        return f"Fel: kunde inte tolka argumenten till {name}."

    if name == "web_search":
        if not config.brave_api_key:
            return "Fel: web search ar inte konfigurerat (BRAVE_API_KEY saknas)."
        try:
            return web_search(args.get("query", ""), config.brave_api_key)
        except httpx.HTTPError as err:
            return f"Sokfel: {err}"

    if name == "doc_search":
        return rag.format_results(rag.retrieve(args.get("query", ""), config))

    return f"Okant verktyg: {name}"
