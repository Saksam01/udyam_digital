# Udyam Digital, Accel Business

A digital-first journey that takes a small Indian business from "what do I need?" to "my services are live"
on a phone, in its own language. Built for the Airtel SYNC 2026 hackathon (Track A).

- **Live app:** https://udyamdigital-apps.vercel.app
- **Back office:** https://udyamdigital-apps.vercel.app/admin
- **API docs:** https://udyam-api-grmtzh7dwq-el.a.run.app/docs

The idea throughout is that code decides and language explains. Prices, eligibility, KYC verdicts and lead
scores come from rules and models we can inspect. The language model only helps understand what the owner
says and rephrases replies (a keyword reader takes over if it is unavailable), and a validator blocks any
number in a reply that the engine did not produce.

## What it does

**For the business owner (customer app)**
- **Advisor** in 8 languages (English, Hindi, Tamil, Telugu, Bengali, Marathi, Kannada, Punjabi), by voice or
  by tapping and typing. One sentence such as "2-doctor clinic in Jaipur, need fast Wi-Fi and WhatsApp
  reminders" fills every answer it contains, and only the missing questions are asked. It covers business type,
  staff, locations, city, GST and needs (in plain outcomes, not product names), then sizes a bundle from the
  25-product catalogue.
- **Plan** with one monthly price, GST shown separately, quantities that can be changed with +/-, and add-ons
  that can be switched on or off. Every change is re-checked against the catalogue rules (city tier, GSTIN,
  minimum size, required base products). Adding an add-on brings the connection it needs with it, and a
  connection that other items depend on cannot be removed.
- **Verify (Smart KYC)** after a DPDP consent screen: upload GST certificate, signatory ID, address proof and
  optionally Udyam. Documents are read with OCR and checked against the GST and Udyam registries. Outcome is
  PASS (setup starts), REVIEW (a person checks) or REJECT (customer is told exactly what to fix). Phone photos
  are straightened, turned upright and evened out for shadows before reading.
- **Resume** on any phone: each order gets a 6-digit code. The order ID or the owner's mobile number plus that
  code reopens the application, so an owner can stop to fetch a certificate from their CA and carry on later.
- **Track** each service through visit, setup and go-live, with the local engineer and partner. Updates arrive
  live, without refreshing.

**For Accel (back office, `/admin`)**
- **Sales console:** live leads from the app, 5,000 historical leads ranked by chance to activate (with the
  working shown on hover), one-click WhatsApp quote and hand-off to the local partner, all orders, fulfilment.
- **Verification desk:** the only place that sees document images. Each case opens a rule-by-rule audit:
  what was read, what it was compared to, the similarity score and threshold, and where on the page it was found.
- In this prototype one password box decides the desk; this is a demo-only role switcher for judges. Production
  would use single sign-on (OAuth 2.0 / OpenID Connect) with short-lived JWTs, role-based access and an audit log
  entry for every document view. Sales never sees customer documents.

## How it works

```
 Browser (phone or laptop)
      │
      ▼
 Vercel: Next.js frontend  ── REST + Server-Sent Events ──►  Google Cloud Run: FastAPI backend
 customer app and /admin                                     rules, OCR, scoring, orders, SQLite
                                                             calls Sarvam (voice) and Gemini (understanding, wording)
```

| Part | How |
|---|---|
| Bundle and price | Profiles per business type sized by staff and sites, checked by a rule engine built from `product_catalogue.csv`. Prices are catalogue list prices, never generated text. |
| KYC | Tesseract OCR with deskewing and watermark removal, GSTIN checksum, registry status, name matching (Levenshtein, sequence and token-sort, plus a distinctive-word check), 28 rules in total. The name typed in the app must match the documents, and the address proof must be in the city where services go in. |
| Lead score | L2-regularised logistic regression trained on `smb_leads.csv` (held-out AUC 0.70). Shown as the stage's historical activation rate times this lead's lift, with the factors that moved it. |
| Order lifecycle | One-way state machine: quote accepted → consent and documents → verified → field dispatch → live. Nothing goes live without verification. |
| Live updates | Server-Sent Events for both the customer tracker and the console. |
| Access | Each order has a private key held by the customer's browser, recoverable with the resume code (5 tries per 15 minutes). Back office calls need a sales or verifier login. |

## Data and privacy (DPDP Act, 2023)

- Consent is recorded as an immutable JSON artifact with a SHA-256 seal, and can be withdrawn from the app.
- Document images are read in memory and not stored when the rules decide on their own.
- Only cases that need a person keep a cleaned page image, encrypted (Fernet), deleted when the reviewer decides,
  when consent is withdrawn, or after 30 days.
- Aadhaar numbers keep only the last 4 digits, in extracted text and on page images. PAN is masked too.
- The order keeps the fields the rules used (masked), the verdict and the audit trail for 180 days.

## Repository layout

```
udyam-digital/
├─ services/core/          FastAPI backend
│  ├─ app.py               HTTP API
│  ├─ udyam/               rules, KYC, OCR, scoring, orders, privacy, voice
│  ├─ data/                hackathon dataset: catalogue, registries, leads, 12 sample applicants
│  ├─ tests/               pytest
│  └─ Dockerfile           container used for Cloud Run
└─ apps/web/               Next.js frontend: customer app (/) and back office (/admin)
   ├─ app/                 pages and styles
   ├─ components/          advisor, plan, KYC, tracker, sales console, verification desk
   └─ lib/                 API client, translations, voice
```

## Run it locally

Needs Python 3.10+, Node.js 18+ and [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) for reading
documents. Use two terminals.

**Backend**
```bash
cd services/core
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
.venv\Scripts\python.exe -m uvicorn app:app --reload --port 8000
```
On macOS or Linux use `.venv/bin/python` and `cp`. Tests: `.venv\Scripts\python.exe -m pytest -q`.

**Frontend**
```bash
cd apps/web
npm install
npm run dev
```
Open http://localhost:3000 and http://localhost:3000/admin. For a faster start when presenting, use
`npm run demo` (builds once, then serves the finished app).

### Settings (`services/core/.env`)

| Variable | Purpose |
|---|---|
| `ADMIN_PASSWORD`, `VERIFIER_PASSWORD` | Sales console and verification desk logins |
| `SARVAM_API_KEY` | Voice (speech to text and text to speech). Without it the browser's own voice is used. |
| `GEMINI_API_KEY` | Free-text advisor answers and replies phrased in the customer's language. Optional. |
| `KYC_VAULT_KEY` | Encryption key for review documents. Generated into `data/.vault_key` if not set. |
| `DEMO_MODE` | `1` lets the customer app run the 12 sample applicants. Set `0` for real customers. |
| `ID_VALIDATION_MODE`, `AS_OF_DATE` | `mock` relaxes four dataset-specific conventions; `2026-07-15` is the dataset's reference date. |
| `OCR_WORKERS` | How many documents are read in parallel (default 4). |

The frontend reads `NEXT_PUBLIC_API_BASE` for the backend address (default `http://127.0.0.1:8000`).

## Demo tips

- `?demo=1` shows the 12 sample applicants (K01-K12) on the Verify screen of that device. `?demo=0` hides them.
- `?new=1`, or "Start for another business" on Home, starts a fresh customer journey.
- The verification desk has a KYC samples page that runs OCR on all 12 and opens the audit for each.

## Deployment

- **Frontend:** Vercel, root directory `apps/web`, with `NEXT_PUBLIC_API_BASE` set to the backend URL.
  Every push to `main` redeploys.
- **Backend:** Google Cloud Run from `services/core` (the Dockerfile installs Tesseract):
  ```bash
  gcloud run deploy udyam-api --source . --region asia-south1 --allow-unauthenticated --memory 2Gi --cpu 1 --max-instances 1 --env-vars-file env.yaml
  ```
  `env.yaml` holds the settings above and is never committed. One instance keeps a single database; data
  created in the app resets when the service restarts, and the historical leads reload on start.

## Authors

Saksam Saraff · Shyam Sundar Karmakar
