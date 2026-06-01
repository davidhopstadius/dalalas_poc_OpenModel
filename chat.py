"""Ateranvandbar klient mot Grunden.ai:s OpenAI-kompatibla API.

Anvands antingen som bibliotek:

    from chat import GrundenChat
    bot = GrundenChat()
    print(bot.ask("Hej!"))

eller som interaktiv CLI:

    python chat.py
"""
from __future__ import annotations

from openai import OpenAI, OpenAIError

from config import Config, ConfigError, load_config

Message = dict[str, str]


class GrundenChat:
    """Haller en konversation med historik mot Grunden.ai."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or load_config()
        self.client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
        )
        self.history: list[Message] = []
        if self.config.system_prompt:
            self.history.append(
                {"role": "system", "content": self.config.system_prompt}
            )

    def ask(self, prompt: str) -> str:
        """Skicka ett meddelande, lagg svaret i historiken och returnera det."""
        self.history.append({"role": "user", "content": prompt})
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=self.history,
        )
        answer = response.choices[0].message.content or ""
        self.history.append({"role": "assistant", "content": answer})
        return answer

    def reset(self) -> None:
        """Nollstall historiken (behaller ev. systemprompt)."""
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

    print(f"Grunden-chatt  (modell: {bot.config.model})")
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

        try:
            answer = bot.ask(prompt)
        except OpenAIError as err:
            print(f"API-fel: {err}\n")
            # Ta bort det obesvarade meddelandet sa historiken halls ren
            if bot.history and bot.history[-1]["role"] == "user":
                bot.history.pop()
            continue

        print(f"\n{answer}\n")


if __name__ == "__main__":
    raise SystemExit(run())
