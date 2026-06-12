# PocGrunden

Chatt-app mot Grunden.ai:s OpenAI-kompatibla API, med **web search** (via Brave),
**reasoning/thinking** och **dokumentsokning (RAG)** i tekniska manualer.
POC pa vag mot en chatbot for lastekniker i falt.

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
| `GRUNDEN_SEARCH` | `1` | Web search pa/av (1=pa, 0=av) |
| `BRAVE_API_KEY` | – | Brave Search-nyckel. Kravs for att sokning ska fungera. |
| `GRUNDEN_DOC_SEARCH` | `1` | Dokumentsokning (RAG) pa/av |
| `GRUNDEN_EMBED_MODEL` | `bge-m3` | Embeddingmodell for indexering/sokning |
| `RAG_INDEX_DIR` | `rag_index` | Mapp dar indexet sparas |
| `RAG_TOP_K` | `5` | Antal traffar som hamtas per dokumentsokning |
| `GRUNDEN_RERANK` | `1` | Reranking (Steg 2) pa/av. Kan ocksa slas av/pa live med `/rerank` |
| `GRUNDEN_RERANK_MODEL` | `bge-reranker-v2-m3` | Rerank-modell (cross-encoder) |
| `RAG_RERANK_CANDIDATES` | `20` | Antal dense-traffar som skickas till rerankern |
| `GRUNDEN_SYSTEM_PROMPT` | – | Egen systemprompt (annars en standard med dagens datum) |

## Dokumentsokning (RAG)

Lagg tekniska manualer (PDF) i mappen `documents/` och indexera dem:

```powershell
python ingest.py            # indexerar alla PDF:er i documents/
python ingest.py minfil.pdf # eller en specifik fil/mapp
```

Inlasningen sker lokalt med PyMuPDF (tabeller halls intakta), texten embeddas
via Grundens `bge-m3` och sparas i `rag_index/`. I chatten exponeras detta som
verktyget `doc_search` – modellen soker i manualerna och svarar med
**sidhanvisning** till kallan. Kor `python ingest.py` igen nar du vill lagga
till fler dokument. Bade `documents/` och `rag_index/` ar gitignorerade.

## Reranking (Steg 2) – pa/av live

Dense-sokningen (cosine) hittar ratt sida i de flesta fall men missar ibland
fragor som kraver exakt formulering (standarder, kontrollfragor). **Steg 2**
hamtar darfor fler dense-kandidater och later Grundens **BGE cross-encoder**
(`bge-reranker-v2-m3`) omsortera dem innan de basta `RAG_TOP_K` valjs.

Spaken ar gjord for att kunna utforskas live i ett kundmote:

- I chatten: `/rerank on` / `/rerank off` (eller `/rerank` for att se laget).
- I kommande GUI: satt `config.rerank` per fraga.
- Som standard fran `.env`: `GRUNDEN_RERANK`.

Flaggan lases vid varje fraga, sa man kan stalla samma fraga med och utan
reranking och jamfora svaren direkt. Slar endpointen fel faller sokningen
tillbaka pa ren dense.

## Sa stangs gapet mot webb-GUI:t

Grundens API har ingen inbyggd web search. Appen aterskapar GUI:ts beteende
med standard function calling: modellen ber om en sokning (`web_search`),
appen kor sokningen mot Brave och matar tillbaka resultaten, varpa modellen
svarar grundat pa farsk fakta. Reasoning slas pa via `thinking`-parametern.

## Utvardering av dokumentsokning

`eval.py` mater retrieval-kvalitet (recall@k) mot ett testset med facit
([eval/questions.jsonl](eval/questions.jsonl)). Varje korning sparas i
`eval/results/<label>.json` sa resultat kan jamforas over tid:

```powershell
python eval.py --no-rerank --label steg1            # spara dense-baslinje
python eval.py --rerank --label steg2 --compare steg1  # rerank + skillnad mot baslinjen
```

`--rerank`/`--no-rerank` tvingar laget for korningen (annars galler `GRUNDEN_RERANK`),
sa samma testset kan koras bada vagarna och jamforas.

## Anvanda som bibliotek

```python
from chat import GrundenChat

bot = GrundenChat()
print(bot.ask("Hej!"))
```

## Struktur

- [config.py](config.py) – laddar/validerar konfiguration fran `.env`
- [chat.py](chat.py) – `GrundenChat`-klassen + interaktiv CLI-loop
- [tools.py](tools.py) – function-calling-verktyg (`web_search`, `doc_search`)
- [rag.py](rag.py) – lokalt RAG-index: embeddings, sokning
- [ingest.py](ingest.py) – CLI for att indexera PDF-dokument fran `documents/`
- [eval.py](eval.py) – mater retrieval-kvalitet (recall@k) mot facit, sparar/jamfor korningar
