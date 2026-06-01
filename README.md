# PocGrunden

Liten chatt-app mot Grunden.ai:s OpenAI-kompatibla API, med **web search**
(via Brave) och **reasoning/thinking** for svar i niva med leverantorens
webb-GUI.

## Kom igang

```powershell
# 1. Skapa och aktivera virtuell miljo
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Installera beroenden
pip install -r requirements.txt

# 3. Konfigurera nyckel
copy .env.example .env
# ...fyll i GRUNDEN_API_KEY i .env

# 4. Kor den interaktiva chatten
python chat.py
```

## Konfiguration

Satts i `.env` (se [.env.example](.env.example)):

| Variabel | Standard | Beskrivning |
|----------|----------|-------------|
| `GRUNDEN_API_KEY` | – (krävs) | API-nyckel |
| `GRUNDEN_BASE_URL` | `https://api.grunden.ai/v1` | API-endpoint |
| `GRUNDEN_MODEL` | `glm-5.1` | Modellnamn |
| `GRUNDEN_THINKING` | `1` | Reasoning/thinking-lage (1=pa, 0=av) |
| `BRAVE_API_KEY` | – | Brave Search-nyckel. Utan den stangs web search av. |
| `GRUNDEN_SYSTEM_PROMPT` | – | Egen systemprompt (annars en standard med dagens datum) |

## Sa stangs gapet mot webb-GUI:t

Grundens API har ingen inbyggd web search. Appen aterskapar GUI:ts beteende
med standard function calling: modellen ber om en sokning (`web_search`),
appen kor sokningen mot Brave och matar tillbaka resultaten, varpa modellen
svarar grundat pa farsk fakta. Reasoning slas pa via `thinking`-parametern.

## Anvanda som bibliotek

```python
from chat import GrundenChat

bot = GrundenChat()
print(bot.ask("Hej!"))
```

## Struktur

- [config.py](config.py) – laddar/validerar konfiguration fran `.env`
- [chat.py](chat.py) – `GrundenChat`-klassen + interaktiv CLI-loop
- [tools.py](tools.py) – function-calling-verktyg (web search via Brave)
