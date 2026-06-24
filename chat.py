"""Ateranvandbar klient mot Grunden.ai:s OpenAI-kompatibla API.

Anvands antingen som bibliotek:

    from chat import GrundenChat
    bot = GrundenChat()
    print(bot.ask("Hej!"))

eller som interaktiv CLI:

    python chat.py
"""
from __future__ import annotations

import json
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
    """Konversation mot en OpenAI-kompatibel leverantor (Grunden eller Berget).

    Anslutningen (base_url/model/api_key) tas fran config.active_llm(), sa samma
    klass driver bade Grunden (default, oforandrat beteende) och Berget.
    """

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or load_config()
        conn = self.config.active_llm()
        self.model = conn.model
        self.client = OpenAI(
            api_key=conn.api_key,
            base_url=conn.base_url,
            timeout=self.config.request_timeout,
            # Tygla backoff sa en trog leverantor inte staplar langa vantor.
            max_retries=1,
        )
        self.history: list[Message] = []
        # Tokenforbrukning for den senaste ask()-fragan (summerat over alla
        # verktygsrundor). Nollstalls i borjan av varje ask().
        self.usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        system = self.config.system_prompt or default_system_prompt(self.config)
        self.history.append({"role": "system", "content": system})

    def _create(self):
        kwargs = {
            "model": self.model,
            "messages": self.history,
            "stream": True,
            # Be API:t inkludera token-anvandning i en sista stream-chunk.
            "stream_options": {"include_usage": True},
        }
        schemas = tools.schemas(self.config)
        if schemas:
            kwargs["tools"] = schemas
            kwargs["tool_choice"] = "auto"
        # thinking-flaggan ar Grunden-specifik (boolean i extra_body). Skicka den
        # bara for Grunden - Berget-modeller kanner inte nodvandigtvis till den.
        if self.config.provider == "grunden":
            kwargs["extra_body"] = {"thinking": self.config.thinking}
        return self.client.chat.completions.create(**kwargs)

    def _consume_stream(self, stream, on_token) -> tuple[str, list[dict], dict | None]:
        """Las en streamad completion: skriv ut innehallet via on_token medan det
        kommer, och aterskapa ev. tool_calls (som kommer i fragment).

        Returnerar aven ev. token-usage (kommer i en separat sista chunk nar
        stream_options.include_usage ar pa)."""
        parts: list[str] = []
        calls: dict[int, dict] = {}
        usage: dict | None = None
        for chunk in stream:
            chunk_usage = getattr(chunk, "usage", None)
            if chunk_usage is not None:
                usage = {
                    "prompt_tokens": chunk_usage.prompt_tokens or 0,
                    "completion_tokens": chunk_usage.completion_tokens or 0,
                    "total_tokens": chunk_usage.total_tokens or 0,
                }
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
        return "".join(parts), tool_calls, usage

    def ask(self, prompt: str, on_tool=None, on_token=None, on_tool_result=None) -> str:
        """Skicka ett meddelande, kor ev. verktyg, och returnera svaret.

        Svaret streamas: on_token(text) anropas for varje bit medan den kommer.
        on_tool(name, arguments) anropas nar modellen begar ett verktyg och
        on_tool_result(name, result) nar verktyget kort (t.ex. for att plocka ut
        kallcitat). Alla callbacks ar valfria - utan dem fungerar metoden som
        vanligt och returnerar hela svaret som strang (vid biblioteksanvandning).
        """
        self.history.append({"role": "user", "content": prompt})
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        for _ in range(MAX_TOOL_ROUNDS):
            content, tool_calls, usage = self._consume_stream(self._create(), on_token)
            if usage:
                for key in self.usage:
                    self.usage[key] += usage.get(key, 0)

            # Sallsynt: modellen returnerar en helt tom tur (varken text eller
            # verktygsanrop). Det intraffar oftare med thinking AV och lamnar
            # annars anvandaren helt utan svar. Gor ett (1) omforsok innan vi
            # bygger turen - historiken slutar fortfarande pa user/tool, sa
            # omforsoket ar rent.
            if not tool_calls and not content.strip():
                content, tool_calls, usage = self._consume_stream(self._create(), on_token)
                if usage:
                    for key in self.usage:
                        self.usage[key] += usage.get(key, 0)

            assistant_msg: Message = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            self.history.append(assistant_msg)

            if not tool_calls:
                return content or "(Tomt svar fran modellen - forsok igen.)"

            for tc in tool_calls:
                fn = tc["function"]
                if on_tool:
                    on_tool(fn["name"], fn["arguments"])
                result = tools.run_tool(fn["name"], fn["arguments"], self.config)
                if on_tool_result:
                    on_tool_result(fn["name"], result)
                self.history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    }
                )

        return "(Avbrot: for manga verktygsrundor utan slutgiltigt svar.)"

    def seed_history(self, prior: list[dict]) -> None:
        """Seeda historiken med tidigare turer (systemprompten ligger forst)."""
        self.history = self.history[:1] + [
            {"role": m["role"], "content": m["content"]}
            for m in prior
            if m["role"] in ("user", "assistant") and m["content"]
        ]

    def reset(self) -> None:
        """Nollstall historiken (behaller systemprompten)."""
        self.history = [m for m in self.history if m["role"] == "system"]


def _anthropic_text(message) -> str:
    """Plocka ut all text ur ett Anthropic-svars content-block."""
    return "".join(
        b.text for b in message.content if getattr(b, "type", None) == "text"
    )


class AnthropicChat:
    """Konversation mot Anthropics Messages-API (Claude).

    Samma publika granssnitt som GrundenChat (ask/seed_history/reset, .usage,
    .history, .config) sa servern och CLI:t kan anvanda klasserna utbytbart via
    build_chat(). Systemprompten skickas separat (Anthropic-konvention) och
    historiken innehaller bara user/assistant-turer.
    """

    def __init__(self, config: Config | None = None) -> None:
        import anthropic  # tung/valfri import - bara nar Anthropic-leverantoren anvands

        self.config = config or load_config()
        conn = self.config.active_llm()
        self.model = conn.model
        self.client = anthropic.Anthropic(
            api_key=conn.api_key,
            timeout=self.config.request_timeout,
            max_retries=1,
        )
        self.system = self.config.system_prompt or default_system_prompt(self.config)
        self.history: list[Message] = []  # endast user/assistant
        self.usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    def seed_history(self, prior: list[dict]) -> None:
        self.history = [
            {"role": m["role"], "content": m["content"]}
            for m in prior
            if m["role"] in ("user", "assistant") and m["content"]
        ]

    def _create_kwargs(self) -> dict:
        kwargs: dict = {
            "model": self.model,
            "system": self.system,
            "messages": self.history,
            "max_tokens": self.config.anthropic_max_tokens,
        }
        schemas = tools.anthropic_schemas(self.config)
        if schemas:
            kwargs["tools"] = schemas
        if self.config.thinking:
            # Stabil form som Claude 4.x thinking-modeller stoder. budget < max_tokens.
            budget = max(1024, min(4000, self.config.anthropic_max_tokens - 1024))
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}
        return kwargs

    def _add_usage(self, usage) -> None:
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0
        self.usage["prompt_tokens"] += (usage.input_tokens or 0) + cache_read + cache_create
        self.usage["completion_tokens"] += usage.output_tokens or 0
        self.usage["total_tokens"] = (
            self.usage["prompt_tokens"] + self.usage["completion_tokens"]
        )

    def ask(self, prompt: str, on_tool=None, on_token=None, on_tool_result=None) -> str:
        self.history.append({"role": "user", "content": prompt})
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        for _ in range(MAX_TOOL_ROUNDS):
            with self.client.messages.stream(**self._create_kwargs()) as stream:
                for event in stream:
                    if event.type == "content_block_delta" and getattr(
                        event.delta, "type", None
                    ) == "text_delta":
                        if on_token:
                            on_token(event.delta.text)
                final = stream.get_final_message()

            self._add_usage(final.usage)
            # Spara assistentens rasvar (inkl. ev. thinking/tool_use-block) i historiken.
            self.history.append({"role": "assistant", "content": final.content})

            if final.stop_reason != "tool_use":
                return _anthropic_text(final)

            tool_results = []
            for block in final.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                arguments = json.dumps(block.input, ensure_ascii=False)
                if on_tool:
                    on_tool(block.name, arguments)
                result = tools.run_tool(block.name, arguments, self.config)
                if on_tool_result:
                    on_tool_result(block.name, result)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )
            self.history.append({"role": "user", "content": tool_results})

        return "(Avbrot: for manga verktygsrundor utan slutgiltigt svar.)"

    def reset(self) -> None:
        """Nollstall historiken (systemprompten ligger separat och behalls)."""
        self.history = []


def build_chat(config: Config | None = None):
    """Returnera ratt chatt-klient for den aktiva leverantoren.

    Grunden/Berget -> GrundenChat (OpenAI-kompatibel). Anthropic -> AnthropicChat.
    """
    cfg = config or load_config()
    if cfg.active_llm().kind == "anthropic":
        return AnthropicChat(cfg)
    return GrundenChat(cfg)


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
    conn = config.active_llm()
    return (
        f"leverantor: {config.provider} | modell: {conn.model} | webbsok: {web} | "
        f"doksok: {docs} | rerank: {rerank} | thinking: {think}"
    )


def run() -> int:
    """Interaktiv chatt-loop. Returnerar processens exit-kod."""
    try:
        bot = build_chat()
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
