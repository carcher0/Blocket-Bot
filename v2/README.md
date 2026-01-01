# Blocket Bot 2.0

**AI-Driven Purchase Assistant for Used Goods on Blocket**

A modern, domain-agnostic evaluation system that helps you find the best deals on Blocket.

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- MySQL Server (for storing run history)
- OpenAI API key (for AI features)

### Installation

```bash
# 1. Navigate to project
cd "c:\github projket\Blocket-Bot"

# 2. Create/activate virtual environment
py -m venv .venv
.\.venv\Scripts\activate

# 3. Install dependencies
pip install -r v2/requirements.txt

# 4. Configure environment
# Create .env file with:
# OPENAI_API_KEY=your-key-here
# MYSQL_PASSWORD=your-password (if needed)
```

### Running the App

```bash
# Option 1: Use run script
python run_v2.py

# Option 2: Direct streamlit
streamlit run v2/ui/app.py
```

Opens at `http://localhost:8502`

---

## 📋 Features

### 🔍 Smart Search
- Enter any product query ("iPhone 15", "cykel 26 tum", "IKEA soffa")
- AI analyzes the market and discovers relevant attributes

### 🎯 Dynamic Preferences
- Preference questions generated based on what's actually in listings
- Support for conditions, price ranges, locations, shipping

### 📊 Transparent Scoring
- **Value Score**: Price vs market (based on comparable listings)
- **Preference Score**: How well it matches your requirements
- **Risk Score**: Detected red flags and missing info

### 💬 Seller Questions
- AI-generated questions to ask sellers about missing info
- Ready to copy-paste

### 📈 Debug Panel
- Full transparency into scoring decisions
- Export results as JSON

---

## 🏗️ Architecture

```
v2/
├── models/         # Pydantic data contracts
│   ├── listing.py
│   ├── discovery.py
│   ├── preferences.py
│   ├── enrichment.py
│   ├── scoring.py
│   └── export.py
├── client/         # Blocket API wrapper
├── ai/             # LLM client + domain discovery
├── pipeline/       # Evaluation pipeline
│   ├── filter.py       # Candidate filtering
│   ├── enrichment.py   # Attribute extraction
│   ├── comps.py        # Market statistics
│   ├── scoring.py      # Deterministic scoring
│   └── orchestrator.py # Pipeline runner
├── ui/             # Streamlit frontend
│   ├── app.py          # Main app
│   ├── styles.py       # CSS theme
│   └── components/     # UI components
└── tests/          # Test suite
```

### Pipeline Flow

```
Query → Fetch → Discovery → Preferences → Filter → Enrich → Score → Top 10
```

1. **Fetch**: Get listings from Blocket API
2. **Discovery**: AI analyzes listings to understand the domain
3. **Preferences**: User answers dynamic questions
4. **Filter**: Reduce to ~50 candidates
5. **Enrich**: Extract attributes, detect risks
6. **Score**: Deterministic scoring with breakdown
7. **Top 10**: Ranked results with explanations

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest v2/tests/ -v

# Run with coverage
python -m pytest v2/tests/ --cov=v2 --cov-report=term-missing
```

---

## 📦 Data Contracts

All AI responses are validated with Pydantic:

- `DomainDiscoveryOutput`: Inferred schema from listings
- `PreferenceProfile`: User selections
- `EnrichedListing`: Extracted attributes + risks
- `ScoringBreakdown`: Transparent score components
- `FullRunExport`: Complete run trace

---

## 🔧 Configuration

Edit `.env` or `v2/config.py`:

```python
# API
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o  # or gpt-5.2

# Database
MYSQL_HOST=localhost
MYSQL_DATABASE=blocket_bot_v2

# Pipeline
DISCOVERY_SAMPLE_SIZE=30
CANDIDATE_LIMIT=50
TOP_K=10
```

---

## 🎨 UI Theme

Blocket-inspired design:
- **Primary**: #0077B5 (Blue)
- **Accent**: #FFD200 (Yellow)
- **Background**: #0D1117 (Dark)

Custom CSS in `v2/ui/styles.py`.

---

## 📝 License

MIT
