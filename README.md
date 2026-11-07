# Udyam Digital, Accel Business

A digital-first acquisition and onboarding journey for Indian MSMEs, built for the Airtel SYNC 2026
hackathon (Track A). A conversational, multilingual, voice-enabled advisor sizes the right bundle,
quotes a single transparent price, runs Smart KYC against the GST/Udyam registries, and tracks
activation, on a phone, in the customer's own language.

The guiding principle is **deterministic guardrails**: a thin conversational layer on top of code
that decides every price, eligibility rule and KYC verdict, with an output validator that blocks any
figure the engine did not produce.

## Repository layout

```
udyam-digital/
├─ services/core/        FastAPI backend, quote engine, Smart KYC, advisor, lead scoring
│  ├─ app.py             HTTP API
│  ├─ udyam/             core logic (quote_engine, kyc_engine, validator, recommender, …)
│  ├─ data/              the provided dataset (catalogue, registries, KYC fixtures + images)
│  └─ tests/             pytest: quotes, KYC verdicts, OCR, orders, consent
└─ apps/web/             Next.js frontend: customer app (/) and back office (/admin)
   ├─ app/               pages + styling
   ├─ components/        advisor, plan, KYC, tracker, sales console, verification desk
   └─ lib/               API client, translations for 8 languages, voice
```

## Backend, run it

Requires Python 3.10+.

```bash
cd services/core
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt     # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # macOS/Linux
.venv\Scripts\python.exe -m uvicorn app:app --reload --port 8000
```

- Interactive API docs: http://127.0.0.1:8000/docs
- Run the tests: `pytest -q` (quotes, the 12 KYC verdicts with and without OCR, order lifecycle, consent)

Key endpoints: `POST /api/v1/quotes`, `POST /api/v1/advisor/messages`,
`POST /api/v1/kyc/assess`, `GET /api/v1/kyc/assess-all`, `GET /api/v1/catalogue`.

## Frontend, run it

Requires Node.js 18+.

```bash
cd apps/web
npm install
npm run dev
```

Open http://localhost:3000. The frontend talks to the backend on port 8000 (override with
`NEXT_PUBLIC_API_BASE` in `.env.local`). Use Chrome or Edge for voice.

## Features

- **Conversational advisor**, asks business type, staff, locations, city, current tools and GST one
  question at a time; answer by tapping, typing, or speaking.
- **Voice + languages**, choose Text or Voice at the start; in Voice mode the advisor speaks each
  question and listens for the answer hands-free. English and Hindi are fully localised, with more
  Indian languages available for voice.
- **Deterministic quotes**, exact, in-range prices and eligibility straight from the catalogue; an
  output validator guarantees no invented figures.
- **Smart KYC**, validates GST checksum, registry status, name matches, document freshness and
  signatory authority; returns PASS / REVIEW / REJECT with reasons.
- **Order tracker**, per-item activation timeline.

## Back office

Open http://localhost:3000/admin. The password decides the desk: `ADMIN_PASSWORD` opens the sales
console, `VERIFIER_PASSWORD` the verification desk. Only the verification desk sees document pages.

## Demo samples

The 12 sample applicants (K01-K12) can be run from the customer app only in demo mode: open
`http://localhost:3000/?demo=1` once on the device (`?demo=0` hides them again). The server allows
them while `DEMO_MODE=1`; set `DEMO_MODE=0` or `APP_ENV=production` for real customers.

## Data & validation modes

KYC runs in `mock` mode by default, which relaxes exactly the four dataset-specific conventions
(PAN 4th-char X, Udyam district 00, Karnataka code KR, and the fixed demo date `2026-07-15`).
Set `ID_VALIDATION_MODE=production` for real-world rules.

## Authors

Saksam Saraff · Shyam Sundar Karmakar
