# Blocket Bot - Testpanel

En lokal Streamlit-baserad testpanel för att söka efter annonser på Blocket, hantera bevakningar och exportera resultat som normaliserad JSON.

## 🚀 Snabbstart

### Förutsättningar

- Python 3.10 eller senare
- MySQL Server (lokalt installerad och igång)

### Installation

1. **Klona/öppna projektet:**
   ```bash
   cd "c:\github projket\Blocket-Bot"
   ```

2. **Skapa och aktivera virtuell miljö:**
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\activate
   ```

3. **Installera beroenden:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Konfigurera MySQL:**
   
   Öppna `storage.py` och uppdatera `DB_CONFIG` om du har ett lösenord:
   ```python
   DB_CONFIG = {
       "host": "localhost",
       "user": "root",
       "password": "ditt_lösenord",  # Ändra här
       "database": "blocket_bot",
   }
   ```
   
   Databasen `blocket_bot` skapas automatiskt vid första körning.

### Körning

```bash
streamlit run app.py
```

Appen öppnas automatiskt i din webbläsare på `http://localhost:8501`.

## 📋 Funktioner

### 🔍 Sökning
- Fri textsökning (t.ex. "iPhone 15")
- Valfria filter: plats, sortering
- Resultat visas i tabell
- Exportera till JSON

### 👁️ Bevakningar
- Spara sökningar med namn och preferenser
- Kör bevakningar för att hämta aktuella annonser
- Deduplicering: markerar nya vs sedda annonser
- Full export (alla) eller Delta export (bara nya)

### 📋 Preferenser
Fyll i preferenser som förbereds för framtida värderingslogik:
- Skick (ny/som ny/bra/ok/defekt)
- Inga sprickor
- Minsta batterihälsa
- Prisintervall
- Platskrav
- Leveranskrav
- Övriga krav

## 📁 Exporterad JSON

Filer sparas i `exports/` med format:

```json
{
  "metadata": {
    "exported_at": "2024-12-31T03:30:00+01:00",
    "query": "iPhone 15",
    "watch_id": "uuid-eller-null",
    "filters": { "locations": ["stockholm"], "sort_order": "price_asc" },
    "preferences": { "no_cracks": true, "min_battery_health": 80 },
    "mode": "full"
  },
  "listings": [
    {
      "listing_id": "12345678",
      "url": "https://blocket.se/annons/...",
      "title": "iPhone 15 128GB",
      "price": { "amount": 7500, "currency": "SEK" },
      "location": "Stockholm",
      "published_at": "2024-12-30T10:00:00+01:00",
      "shipping_available": true,
      "fetched_at": "2024-12-31T03:30:00+01:00",
      "raw": { }
    }
  ]
}
```

## 🧪 Tester

```bash
python -m pytest tests/ -v
```

## 📂 Projektstruktur

```
Blocket-Bot/
├── app.py                  # Streamlit-app
├── blocket_client.py       # BlocketAPI wrapper med retry
├── normalization.py        # Pydantic-modeller för export
├── storage.py              # MySQL-persistens
├── requirements.txt        # Beroenden
├── README.md
├── exports/                # Exporterade JSON-filer
└── tests/
    ├── test_normalization.py
    └── test_dedup.py
```

## 🔧 Teknisk info

- **Backend:** Python + [blocket-api](https://pypi.org/project/blocket-api/)
- **UI:** Streamlit
- **Databas:** MySQL
- **Retry:** tenacity (exponentiell backoff)
- **Validering:** Pydantic v2