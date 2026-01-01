# Blocket Bot 2.0 - System Architecture

> **Senast uppdaterad:** 2026-01-01  
> **OBS:** Detta dokument ska alltid hållas uppdaterat när ändringar görs i systemet.

## Översikt

Blocket Bot 2.0 är en AI-driven köpassistent för begagnade varor på Blocket. Systemet analyserar annonser, identifierar produkttyp, ställer anpassade frågor baserat på domän, och rankar resultat baserat på värde, preferensmatchning och risk.

```
┌─────────────────────────────────────────────────────────────────┐
│                         BLOCKET BOT 2.0                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   [Sök] ──► [Discovery] ──► [Preferenser] ──► [Analys] ──► [Resultat]
│                  │                               │              │
│                  ▼                               ▼              │
│            AI identifierar               Pipeline rankar        │
│            produktdomän                  och poängsätter        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Mappstruktur

```
Blocket-Bot/
├── v1/                     # Gamla versionen (arkiverad)
│   ├── app.py
│   ├── blocket_client.py
│   ├── evaluator/
│   └── tests/
│
├── v2/                     # Aktiv version
│   ├── __init__.py
│   ├── config.py           # Konfiguration och env-variabler
│   ├── models/             # Pydantic datamodeller
│   ├── client/             # Blocket API-wrapper
│   ├── ai/                 # LLM-klient och domän-discovery
│   ├── pipeline/           # Utvärderingspipeline
│   ├── ui/                 # Streamlit-gränssnitt
│   └── tests/              # Enhetstester
│
├── run_v2.py               # Startskript
├── requirements.txt        # Beroenden (v1)
├── .env                    # API-nycklar (OPENAI_API_KEY)
└── ARCHITECTURE.md         # Detta dokument
```

---

## Dataflöde

### Steg 1: Sökning
- **Fil:** `v2/client/blocket.py`
- Användaren skriver en sökfråga (t.ex. "RTX 4080")
- `BlocketClient` hämtar annonser från Blocket API
- Normaliserar till `NormalizedListing`-modeller
- **Fält:** `subject` → titel, `share_url` → länk

### Steg 2: Domän-Discovery (AI)
- **Fil:** `v2/ai/domain_discovery.py`
- AI analyserar annonstitlar och beskrivningar
- Identifierar produkttyp (t.ex. "grafikkort")
- Ger **konfidens** (0-100%)
- Om **konfidens < 70%** → ställer följdfråga till användaren

### Steg 3: Preferenser
- **Fil:** `v2/ui/components/preference_form.py`
- Användaren svarar på dynamiska frågor
- Frågor genereras baserat på domän (AI)
- Sparas i `PreferenceProfile`

### Steg 4: Pipeline
- **Fil:** `v2/pipeline/orchestrator.py`

```
Listings ──► Filter ──► Enrich ──► Comps ──► Score ──► Top 10
              │           │          │          │
              ▼           ▼          ▼          ▼
        ~50 kandidater  Extrahera   Marknad   Poäng:
                        attribut    stats     Value 50%
                        Risk flags            Pref 35%
                        Frågor                Risk 15%
```

### Steg 5: Resultat
- **Fil:** `v2/ui/components/result_card.py`
- Visar Top 10 med poäng, pris, beskrivning
- Klickbara länkar till Blocket
- Säljarfrågor att kopiera

---

## Kärnmodeller (Pydantic)

| Modell | Fil | Syfte |
|--------|-----|-------|
| `NormalizedListing` | `models/listing.py` | Normaliserad annons |
| `DomainDiscoveryOutput` | `models/discovery.py` | AI:s domänschema |
| `PreferenceProfile` | `models/preferences.py` | Användarens val |
| `EnrichedListing` | `models/enrichment.py` | Extraherade attribut + risker |
| `ScoringBreakdown` | `models/scoring.py` | Poängdetaljer |
| `RankedListing` | `models/scoring.py` | Slutligt resultat |
| `FullRunExport` | `models/export.py` | Komplett körning |

---

## Poängsättning (Deterministisk)

```
Total = (Value × 0.50) + (Preference × 0.35) + (Risk × 0.15)
```

### Value Score (0-100)
- Jämför pris mot marknadens median
- Billigare än median = högre poäng
- Beräknas i `v2/pipeline/comps.py`

### Preference Score (0-100)
- Hur väl annonsen matchar användarens svar
- Beräknas i `v2/pipeline/scoring.py`

### Risk Score (0-100)
- 100 = ingen risk
- Dras ner för varje riskflagga:
  - Kort beskrivning (-20)
  - Inga bilder (-15)
  - Nytt konto (-10)
  - Brådskandeord (-15)

---

## AI-integration

### LLM-klient
- **Fil:** `v2/ai/llm_client.py`
- Använder OpenAI API (gpt-4o/gpt-5.2)
- Kräver `OPENAI_API_KEY` i `.env`
- JSON-mode för strukturerade svar

### Konfidens + Följdfråga
- **Fil:** `v2/models/discovery.py` → `InferredDomain`
- Om `confidence < 0.7` → `needs_clarification = True`
- AI måste ge `clarifying_question` och `clarifying_options`

---

## Konfiguration

**Fil:** `v2/config.py`

| Variabel | Standard | Beskrivning |
|----------|----------|-------------|
| `OPENAI_API_KEY` | - | API-nyckel för LLM |
| `OPENAI_MODEL` | `gpt-4o` | Modell att använda |
| `CANDIDATE_LIMIT` | 50 | Max kandidater efter filter |
| `MIN_COMPS` | 3 | Minimum jämförbara för prisjämförelse |
| `TOP_K` | 10 | Antal resultat att visa |

---

## Köra systemet

```bash
# 1. Aktivera virtuell miljö
.\.venv\Scripts\activate

# 2. Installera beroenden
pip install -r v2/requirements.txt

# 3. Sätt API-nyckel i .env
OPENAI_API_KEY=sk-...

# 4. Starta
python run_v2.py

# Öppnas på http://localhost:8502
```

---

## Ändringslogg

| Datum | Ändring |
|-------|---------|
| 2026-01-01 | Skapade v2-struktur, alla modeller, pipeline, UI |
| 2026-01-01 | Fixade API-fältmappning (subject→title, share_url→url) |
| 2026-01-01 | Lade till konfidens + följdfråga-system |
| 2026-01-01 | Flyttade v1 till egen mapp |
