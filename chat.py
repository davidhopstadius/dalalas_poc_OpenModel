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
        )
        self.history: list[Message] = []
        system = self.config.system_prompt or default_system_prompt(self.config)
        self.history.append({"role": "system", "content": system})

    def _create(self):
        kwargs = {
            "model": self.config.model,
            "messages": self.history,
        }
        schemas = tools.schemas(self.config)
        if schemas:
            kwargs["tools"] = schemas
            kwargs["tool_choice"] = "auto"
        if self.config.thinking:
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
        return self.client.chat.completions.create(**kwargs)

    def ask(self, prompt: str, on_tool=None) -> str:
        """Skicka ett meddelande, kor ev. verktyg, och returnera svaret.

        on_tool: valfri callback (name, arguments) som anropas nar modellen
        begar ett verktyg - anvands av CLI:t for att visa en sokindikator.
        """
        self.history.append({"role": "user", "content": prompt})

        for _ in range(MAX_TOOL_ROUNDS):
            message = self._create().choices[0].message

            assistant_msg: Message = {"role": "assistant", "content": message.content}
            if message.tool_calls:
                assistant_msg["tool_calls"] = [
                    tc.model_dump() for tc in message.tool_calls
                ]
            self.history.append(assistant_msg)

            if not message.tool_calls:
                return message.content or ""

            for tc in message.tool_calls:
                if on_tool:
                    on_tool(tc.function.name, tc.function.arguments)
                result = tools.run_tool(
                    tc.function.name, tc.function.arguments, self.config
                )
                self.history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )

        return "(Avbrot: for manga verktygsrundor utan slutgiltigt svar.)"

    def reset(self) -> None:
        """Nollstall historiken (behaller systemprompten)."""
        self.history = [m for m in self.history if m["role"] == "system"]


HELP = """Kommandon:
  /reset   nollstall konversationen
  /help    visa denna hjalp
  /exit    avsluta (aven Ctrl+C eller Ctrl+D)
"""


def run() -> int:
    """Interaktiv chatt-loop. Returnerar processens exit-kod."""
    try:
        bot = GrundenChat()
    except ConfigError as err:
        print(f"Konfigurationsfel: {err}")
        return 1

    web = "pa" if bot.config.search_enabled else "av"
    docs = "pa" if (bot.config.doc_search and rag.has_index(bot.config)) else "av"
    think = "pa" if bot.config.thinking else "av"
    print(
        f"Grunden-chatt  (modell: {bot.config.model} | webbsok: {web} | "
        f"doksok: {docs} | thinking: {think})"
    )
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

        def show_tool(name: str, arguments: str) -> None:
            import json
            try:
                args = json.loads(arguments) if arguments else {}
            except json.JSONDecodeError:
                args = {}
            detalj = args.get("query", arguments)
            print(f"  [{name}: {detalj}]")

        try:
            answer = bot.ask(prompt, on_tool=show_tool)
        except OpenAIError as err:
            print(f"API-fel: {err}\n")
            if bot.history and bot.history[-1]["role"] == "user":
                bot.history.pop()
            continue

        print(f"\n{answer}\n")


if __name__ == "__main__":
    raise SystemExit(run())
