# Agricultural AI Assistant

> A personal AI system for managing a Rosa Damascena farm in Bulgaria.
> Built to make agronomic decisions more reliable, reduce operational costs, and automate the administrative burden of small-scale farming.

---

## Why I Built This

I grow 12 decares of oil-bearing rose (*Rosa damascena*) across two parcels in Bulgaria. The decisions I make every season — when to spray, what to use, how much to apply, when to prune, when to fertilize — directly affect yield, quality, and profitability. Getting them wrong is expensive. If getting them badly wrong could lead to lose the entire harvest.

I started this project in April 2026 to build an assistant I can trust with those decisions. Not one that just talks — one that calculates, records, remembers, and warns me when conditions are wrong.

The agent starts with roses because that is what I know best. Once it performs reliably here, I will expand it to other crops and cultures.

---

## What It Can Do Today

### Plant Protection
- Records completed spray operations with products, doses, volume, nozzle type
- Calculates product concentration corrected for row spacing and canopy width (including row correction factor)
- Retrieves 7-day weather forecasts for each parcel (wind, rain, temperature)
- Saves planned sprays to Supabase — with confirmation step before writing, duplicate prevention, and total product amount per item
- Sends Telegram notifications with spray conditions and product amounts for the next 5 days
- Maintains a diagnostic diary of symptoms, diagnoses, and corrections over time
- Searches agronomic literature (PDF, DOCX, MD, XLSX) by keyword — returns only relevant excerpts, never reads full files
- Knows the full phenological calendar of Rosa damascena — determines growth stage automatically from the date
- Never names a disease or pest without verifying it in literature first

### Agrotechnical Operations
- Records field operations: cultivation, disc harrowing, pruning, irrigation, fertilization
- Recommends when to repeat an operation based on elapsed time, weather forecast, and seasonal stage
- Can analyse field photos to assess weed coverage

### Knowledge Base
- `База_знания.md` — structured reference for all major diseases, pests, economic thresholds, spray calendar, and fertilization schedule, extracted from НСРЗ and БАБХ literature
- `preprocess_literature.py` — converts PDF, DOCX, and XLSX files to searchable .md/.txt on demand; auto-detects tables

### Infrastructure
- Streamlit chat interface with image upload and manual model selection
- Claude Haiku by default, Claude Sonnet for images, PDFs, and complex queries
- Telegram bot deployed on Render (24/7, free tier) — send `/проверка` from phone
- Supabase cloud database for planned sprays
- Spray history and agrotechnical diary stored locally in Markdown
- Literature search covers both `05_Литература/` and `03_Препарати_и_Торове/`

### Disease Detection (YOLOv11)
- Analyses field photos locally — no Claude API cost for image analysis
- Detects: Black Spot, Downy Mildew, Powdery Mildew, healthy plants
- Automatically saves photos to the correct category folder: diseases / pests / weeds / healthy
- Model: YOLOv11n trained on 3702 images, mAP50 = 0.921
- Future versions: pests (aphids, spider mites), weeds

---

## Architecture

I am building this as a multi-agent system. Each domain gets its own specialist. One general agent coordinates and delegates.

```
┌─────────────────────────────────────────────┐
│             Streamlit Interface              │
└─────────────────────┬───────────────────────┘
                      │
┌─────────────────────▼───────────────────────┐
│              Coordinator Agent               │
│         routes requests to specialists       │
└──────┬──────────┬──────────┬────────┬───────┘
       │          │          │        │
       ▼          ▼          ▼        ▼
   Plant       Nutrition  Financial  Admin
  Protection   Agent      Agent      Agent
   Agent
       │          │          │        │
       └──────────┴──────────┴────────┘
                       │
          ┌────────────▼────────────┐
          │         Supabase        │
          │    (shared memory)      │
          └─────────────────────────┘
                       │
          ┌────────────▼────────────┐
          │      Telegram Bot       │
          │  (notifications, /check)│
          └─────────────────────────┘
```

### Decision Safety Levels

The agent operates with three levels of authority:

| Level | Action | Examples |
|---|---|---|
| ✅ Auto | Executes immediately | Log a spray, calculate a dose, check weather |
| ⚠️ Propose | Recommends, waits for confirmation | Spray recommendation, fertilizer plan |
| 🔴 Inform only | Provides information, never decides | New product first use, soil correction without analysis |

---

## Roadmap

### Phase 1 — Plant Protection *(in progress, 2026 season)*
- [x] Spray diary and history
- [x] Concentration calculator with row correction
- [x] Weather integration (Open-Meteo)
- [x] Planned sprays with cloud storage (Supabase)
- [x] Telegram notifications with product amounts
- [x] Diagnostic diary (local agent memory)
- [x] Literature search — keyword search across PDF, DOCX, MD, XLSX
- [x] Literature preprocessing script (PDF/DOCX/XLSX → MD/TXT, table-aware)
- [x] Phenological calendar built into the agent
- [x] Structured knowledge base (База_знания.md)
- [x] Confirmation step before writing planned sprays
- [x] Duplicate spray prevention
- [ ] Mark sprays as completed via chat
- [ ] БАБХ official diary auto-fill (.docx)
- [ ] Soil analysis input for fertilizer baseline

### Phase 2 — Nutrition Module *(2026–2027)*
- [ ] Soil analysis input and interpretation
- [ ] Leaf analysis input and interpretation
- [ ] Fertilization calendar with product recommendations
- [ ] NPK balance tracking per parcel
- [ ] Integration with Phase 1 (no spraying during fertilization windows)

### Phase 3 — Agrotechnical Operations *(started 2026-04-22)*
- [x] Agrotechnical diary (cultivation, pruning, irrigation, fertilization)
- [x] Recommendation engine — elapsed time + weather + season + photo
- [ ] Pruning calendar with timing recommendations
- [ ] Irrigation scheduling

### Phase 4 — Financial Module *(2027)*
- [ ] Expense tracking (products, labor, machinery, vehicles, equipment)
- [ ] Revenue tracking per parcel
- [ ] Yield forecasting based on previous seasons
- [ ] Profitability analysis (income vs. cost per decmare)
- [ ] Machinery and equipment maintenance log

### Phase 5 — Administrative Module *(2027–2028)*
- [ ] Fixed deadline calendar (contracts, declarations, APIA forms)
- [ ] Real-time monitoring of ДФЗ announcements for emergency subsidy programs
- [ ] Document reminders with lead time warnings
- [ ] Web search integration for new programs and regulations

### Phase 6 — Multi-crop Expansion *(future)*
- [ ] Generalize agents beyond Rosa Damascena
- [ ] Support for other Bulgarian crops

---

## Tech Stack

| Component | Technology |
|---|---|
| Interface | Streamlit |
| AI | Claude API (Anthropic) — Haiku + Sonnet |
| Database | Supabase (PostgreSQL) |
| Notifications | Telegram Bot API |
| Bot hosting | Render (free tier) |
| Weather | Open-Meteo API |
| Disease Detection | YOLOv11n (Ultralytics) — local inference |
| Local storage | Markdown files |
| Environment | Python 3, Anaconda |

---

## Project Structure

```
.
├── agent.py              # Claude API logic, tool orchestration, model routing
├── app.py                # Streamlit chat interface
├── tools.py              # All tool implementations
├── config.py             # Parcel coordinates, farm parameters, nozzle specs
├── telegram_bot.py       # Flask webhook bot for Render deployment
├── morning_check.py      # Local script for manual spray condition check
├── preprocess_literature.py  # Converts PDF/DOCX/XLSX to searchable MD/TXT
├── Procfile              # Render deployment configuration
├── requirements.txt      # Python dependencies
├── .env                  # API keys (not committed)
├── 01_Дневник_Операции/  # Spray diary, agrotechnical diary, БАБХ records
├── 02_Администрация/     # Contracts, subsidies, documents
├── 03_Препарати_и_Торове/ # Spray calendar, soil operations, БАБХ register
├── 04_Парцели/           # Parcel data, cadastre, lease agreements
└── 05_Литература/        # Literature, knowledge base, diagnostic diary
```

---

## Data Sources & Citations

This project uses the following publicly available datasets:

**Rose Disease Prediction Dataset**
- Author: vinodk
- Source: https://universe.roboflow.com/vinodk-cb0f7/rose-disease-prediction-yolov5
- License: CC BY 4.0
- Content: 3702 images, 4 classes (Black Spot, Downy Mildew, Normal, Powdery Mildew)

Trained model published on Hugging Face: https://huggingface.co/p7ivanov/rose-disease-detection

We are grateful to the authors for making their data publicly available under open licenses.

If you use this project or the trained model, please cite the dataset above.

---

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

Required `.env` variables:
```
ANTHROPIC_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
SUPABASE_URL=...
SUPABASE_KEY=...
```

---

## Session Log

| Date | What I built |
|---|---|
| 2026-04-21 | Initial setup: Streamlit UI, Claude API with tool use, weather, spray diary, concentration calculator |
| 2026-04-21 | Model routing (Haiku default / Sonnet for images and complex queries), manual model selector in sidebar |
| 2026-04-21 | Literature tools (list_literature, read_literature) for PDF/DOCX/MD |
| 2026-04-21 | Diagnostic diary for symptom memory and corrections |
| 2026-04-21 | Telegram bot, Supabase planned sprays, Render deployment, webhook |
| 2026-04-22 | Rewrote README in English, defined full architecture and roadmap |
| 2026-04-22 | Literature search (keyword-based, PDF/DOCX/MD/XLSX), preprocessing script with table detection |
| 2026-04-22 | Knowledge base (База_знания.md) — diseases, pests, thresholds, spray calendar extracted from НСРЗ/БАБХ |
| 2026-04-22 | Phenological calendar in agent, honesty rules, literature-first disease naming |
| 2026-04-22 | Confirmation step + duplicate prevention for planned sprays; product amount field in Telegram |
| 2026-04-22 | Agrotechnical diary — log cultivation, pruning, irrigation; recommendations from history + weather |
| 2026-04-25 | Photo archive with automatic categorization (diseases/pests/weeds/healthy) |
| 2026-04-25 | YOLOv11n trained on rose disease dataset — integrated into Telegram bot for local inference |
| 2026-04-25 | Renamed folders to Latin (07_Photos, 08_AI_Model) for cross-platform compatibility |
