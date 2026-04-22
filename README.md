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
- Calculates product concentration corrected for row spacing and canopy width
- Retrieves 7-day weather forecasts for each parcel (wind, rain, temperature)
- Saves planned sprays to a cloud database (Supabase)
- Sends Telegram notifications with spray conditions for the next 5 days
- Maintains a diagnostic diary of symptoms, diagnoses, and corrections over time
- Reads agronomic literature (PDF, DOCX, MD) to inform its recommendations

### Infrastructure
- Streamlit chat interface with image upload and manual model selection
- Claude Haiku by default, Claude Sonnet for images, PDFs, and complex queries
- Telegram bot deployed on Render (24/7, free tier) — send `/проверка` from phone
- Supabase cloud database for planned sprays
- All spray history stored locally in Markdown

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
- [x] Planned sprays with cloud storage
- [x] Telegram notifications
- [x] Diagnostic diary (local agent memory)
- [x] Literature reading (PDF, DOCX, MD)
- [ ] Mark sprays as completed
- [ ] БАБХ official diary auto-fill (.docx)
- [ ] Soil analysis input for fertilizer baseline

### Phase 2 — Nutrition Module *(2026–2027)*
- [ ] Soil analysis input and interpretation
- [ ] Leaf analysis input and interpretation
- [ ] Fertilization calendar with product recommendations
- [ ] NPK balance tracking per parcel
- [ ] Integration with Phase 1 (no spraying during fertilization windows)

### Phase 3 — Agrotechnical Operations *(2027)*
- [ ] Pruning calendar with timing recommendations
- [ ] Soil cultivation scheduling
- [ ] Irrigation management

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
├── Procfile              # Render deployment configuration
├── requirements.txt      # Python dependencies
├── .env                  # API keys (not committed)
├── 01_Дневник_Операции/  # Spray diary, БАБХ records, literature
├── 02_Администрация/     # Contracts, subsidies, documents
├── 03_Препарати_и_Торове/ # Product inventory, spray calendar
├── 04_Парцели/           # Parcel data, cadastre, lease agreements
└── 05_Литература/        # Agronomic literature, diagnostic photos
```

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
