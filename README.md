# PocGrunden

Liten chatt-app mot Grunden.ai:s OpenAI-kompatibla API.

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
| `GRUNDEN_SYSTEM_PROMPT` | – | Valfri systemprompt |

## Anvanda som bibliotek

```python
from chat import GrundenChat

bot = GrundenChat()
print(bot.ask("Hej!"))
```

## Struktur

- [config.py](config.py) – laddar/validerar konfiguration fran `.env`
- [chat.py](chat.py) – `GrundenChat`-klassen + interaktiv CLI-loop
