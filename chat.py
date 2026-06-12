"""Ateranvandbar klient mot Grunden.ai:s OpenAI-kompatibla API.

Anvands antingen som bibliotek:

    from chat import GrundenChat
    bot = GrundenChat()
    print(bot.ask("Hej!"))

eller som interaktiv CLI:

    python chat.py
"""
from __future__ import annotations

from datetime import date

from openai import OpenAI, OpenAIError

import rag
import tools
from config import Config, ConfigError, load_config

Message = dict

# Max antal verktygsrundor per fraga, sa vi inte fastnar i en oandlig loop.
MAX_TOOL_ROUNDS = 5


def default_system_prompt(config: Config) -> str:
    today = date.today().isoformat()
    prompt = (
        f"Du ar en hjalpsam assistent for lastekniker. Dagens datum ar {today}. "
        "Svara pa svenska, utforligt och faktagranskat."
    )
    if config.doc_search and rag.has_index(config):
        prompt += (
            " Du har tillgang till verktyget doc_search som soker i indexerad "
            "teknisk dokumentation (installations- och servicemanualer). Anvand "
            "doc_search for fragor om specifika system, felsokning, felkoder, "
            "installation, kopplingar, installningar och artikelnummer. Grunda "
            "svaret pa traffarna och **ange alltid kalla med sidnummer** "
            "(t.ex. 'enligt SW300-manualen, sida 92')."
        )
    if config.search_enabled:
        prompt += (
            " Du har ocksa verktyget web_search. Du MASTE anvanda web_search "
            "innan du svarar pa fragor som ror aktuella handelser, datum, vem "
            "som innehar en post eller titel, nyheter, priser, eller annan fakta "
            "som kan ha andrats efter din traningsdata. Gissa aldrig ur minnet "
            "pa sadana fragor."
        )
    return prompt


class GrundenChat:
    """Haller en konversation med historik mot Grunden.ai."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or load_config()
        self.client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.request_timeout,
        )
        self.history: list[Message] = []
        system = self.config.system_prompt or default_system_prompt(self.config)
        self.history.append({"role": "system", "content": system})

    def _create(self):
        kwargs = {
            "model": self.config.model,
            "messages": self.history,
            "stream": True,
        }
        schemas = tools.schemas(self.config)
        if schemas:
            kwargs["tools"] = schemas
            kwargs["tool_choice"] = "auto"
        if self.config.thinking:
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
        return self.client.chat.completions.create(**kwargs)

    def _consume_stream(self, stream, on_token) -> tuple[str, list[dict]]:
        """Las en streamad completion: skriv ut innehallet via on_token medan det
        kommer, och aterskapa ev. tool_calls (som kommer i fragment)."""
        parts: list[str] = []
        calls: dict[int, dict] = {}
        for chunk in stream:
            if not chunk.choices:  # t.ex. tomma/usage-chunks
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                parts.append(delta.content)
                if on_token:
                    on_token(delta.content)
            for tc in delta.tool_calls or []:
                slot = calls.setdefault(
                    tc.index, {"id": None, "name": "", "arguments": ""}
                )
                if tc.id:
                    slot["id"] = tc.id
                if tc.function and tc.function.name:
                    slot["name"] += tc.function.name
                if tc.function and tc.function.arguments:
                    slot["arguments"] += tc.function.arguments
        tool_calls = [
            {
                "id": c["id"],
                "type": "function",
                "function": {"name": c["name"], "arguments": c["arguments"]},
            }
            for _, c in sorted(calls.items())
        ]
        return "".join(parts), tool_calls

    def ask(self, prompt: str, on_tool=None, on_token=None) -> str:
        """Skicka ett meddelande, kor ev. verktyg, och returnera svaret.

        Svaret streamas: on_token(text) anropas for varje bit medan den kommer.
        on_tool(name, arguments) anropas nar modellen begar ett verktyg.
        Bada ar valfria - utan dem fungerar metoden som vanligt och returnerar
        hela svaret som strang (lampligt nar appen anvands som bibliotek).
        """
        self.history.append({"role": "user", "content": prompt})

        for _ in range(MAX_TOOL_ROUNDS):
            content, tool_calls = self._consume_stream(self._create(), on_token)

            assistant_msg: Message = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            self.history.append(assistant_msg)

            if not tool_calls:
                return content

            for tc in tool_calls:
                fn = tc["function"]
                if on_tool:
                    on_tool(fn["name"], fn["arguments"])
                result = tools.run_tool(fn["name"], fn["arguments"], self.config)
                self.history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    }
                )

        return "(Avbrot: for manga verktygsrundor utan slutgiltigt svar.)"

    def reset(self) -> None:
        """Nollstall historiken (behaller systemprompten)."""
        self.history = [m for m in self.history if m["role"] == "system"]


HELP = """Kommandon:
  /rerank        visa om reranking (Steg 2) ar pa eller av
  /rerank on     sla pa reranking (BGE cross-encoder)
  /rerank off    sla av reranking (ren dense-sokning, Steg 1)
  /reset         nollstall konversationen
  /help          visa denna hjalp
  /exit          avsluta (aven Ctrl+C eller Ctrl+D)
"""


def _status_line(config: Config) -> str:
    web = "pa" if config.search_enabled else "av"
    docs = "pa" if (config.doc_search and rag.has_index(config)) else "av"
    think = "pa" if config.thinking else "av"
    rerank = "pa" if config.rerank else "av"
    return (
        f"modell: {config.model} | webbsok: {web} | doksok: {docs} | "
        f"rerank: {rerank} | thinking: {think}"
    )


def run() -> int:
    """Interaktiv chatt-loop. Returnerar processens exit-kod."""
    try:
        bot = GrundenChat()
    except ConfigError as err:
        print(f"Konfigurationsfel: {err}")
        return 1

    print(f"Grunden-chatt  ({_status_line(bot.config)})")
    print("Skriv ett meddelande. /help for kommandon, /exit for att avsluta.\n")

    while True:
        try:
            prompt = input("Du> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nHej da!")
            return 0

        if not prompt:
            continue
        if prompt in ("/exit", "/quit"):
            print("Hej da!")
            return 0
        if prompt == "/help":
            print(HELP)
            continue
        if prompt == "/reset":
            bot.reset()
            print("(konversationen nollstalld)")
            continue
        if prompt.startswith("/rerank"):
            arg = prompt[len("/rerank"):].strip().lower()
            if arg in ("on", "pa", "1"):
                bot.config.rerank = True
            elif arg in ("off", "av", "0"):
                bot.config.rerank = False
            elif arg:
                print("Anvandning: /rerank [on|off]")
                continue
            print(f"(reranking: {'pa' if bot.config.rerank else 'av'})")
            continue

        def show_tool(name: str, arguments: str) -> None:
            import json
            try:
                args = json.loads(arguments) if arguments else {}
            except json.JSONDecodeError:
                args = {}
            detalj = args.get("query", arguments)
            print(f"  [{name}: {detalj}]")

        # Skriv ut svaret medan det streamas. "Grunden> " visas forst nar forsta
        # token kommer, sa indikatorn ovan inte blandas ihop med svaret.
        started = False

        def show_token(text: str) -> None:
            nonlocal started
            if not started:
                print("\nGrunden> ", end="", flush=True)
                started = True
            print(text, end="", flush=True)

        print("  (tanker...)", flush=True)
        try:
            answer = bot.ask(prompt, on_tool=show_tool, on_token=show_token)
        except OpenAIError as err:
            print(f"\nAPI-fel: {err}\n")
            if bot.history and bot.history[-1]["role"] == "user":
                bot.history.pop()
            continue

        if started:
            print("\n")  # avsluta den streamade raden
        else:
            print(f"\nGrunden> {answer}\n")  # inget streamades (t.ex. tomt svar)


if __name__ == "__main__":
    raise SystemExit(run())
