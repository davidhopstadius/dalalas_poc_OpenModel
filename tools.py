"""Function-calling-verktyg som modellen kan anropa.

Just nu finns ett verktyg: web_search via Brave Search API. Modellen ber om
en sokning (tool_call), vi utfor den har och matar tillbaka resultatet.
"""
from __future__ import annotations

import json

import httpx

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


def schemas(search_enabled: bool) -> list[dict] | None:
    """Returnera tools-schemat som ska skickas till modellen (eller None)."""
    return [WEB_SEARCH_SCHEMA] if search_enabled else None


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

    return f"Okant verktyg: {name}"
