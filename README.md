# FinPilot

FinPilot is a sandbox personal-finance agent for the "AI as a Financial Participant" prototype. It categorizes spending, builds a budget, and can pay a bill or move money into a savings goal only when a deterministic policy engine allows it. There is no real bank and no real money.

The demo persona is an international student with a 1200 USD monthly allowance.

## Architecture

The browser talks to a FastAPI app. The language model never touches SQLite or the bank. It can only call tools, and every tool call goes through `PolicyEngine`, which returns `ALLOW`, `REQUIRE_APPROVAL`, or `DENY` and appends a row to `audit_log`.

- T0 read-only. Money tools are denied and a blocked card is filed.
- T1 propose only. Approval cannot execute.
- T2 execute after the user approves. Approvals expire after 15 minutes.
- T3 execute inside the per-action and daily caps.
- Bill payees must be on the allowlist. Amounts also have a system cap.
- The same idempotency key cannot move money twice.

## Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer
- Optional: Docker, and a free OpenAI-compatible model key (Groq, Gemini's OpenAI-compatible endpoint, or OpenRouter)

## One-command setup

```bash
docker compose up --build
```

The API is on port 8000 and the UI is on port 5173. The container loads the seed on first start. Put `LLM_API_KEY` in a `.env` file beside `docker-compose.yml` if you want live chat. The dashboard, inbox, simulator, and audit log work with no key.

## Windows, without Docker

```powershell
python -m pip install -r backend/requirements.txt
copy .env.example .env
python scripts/seed.py
python -m uvicorn app.main:app --app-dir backend --port 8000
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. API docs are at http://127.0.0.1:8000/docs.

## Environment variables

| Name | Purpose |
| --- | --- |
| `LLM_BASE_URL` | OpenAI-compatible base URL |
| `LLM_API_KEY` | Model key. Never commit this. |
| `LLM_MODEL` | Model name on that host |
| `DATABASE_URL` | SQLite URL. The default file is `backend/data/finpilot.db` |
| `SEED_ON_START` | `1` loads the persona when the database is empty |
| `CHAT_RATE_LIMIT` | Chat requests allowed per minute |

`scripts/seed.py` wipes and reloads the demo user. It is safe to run again.

## Demo script

1. Open the dashboard and read the October budget, goals, and anomaly notes.
2. Open the Approval Inbox and approve the phone bill. The checking balance drops by 35.
3. Open the Audit Log and confirm the execution row. Export the CSV.
4. Open What-if and run "Cancel two subscriptions and cook more". No money moves.
5. If a model key is set, ask in Chat: "How much did I spend on groceries in September?" The answer cites transaction ids. With no key, chat shows a clear error and the rest of the app still loads.

`python scripts/demo_run.py` replays the sandbox flow and writes `docs/evidence/demo-*.json`.

A sample upload lives at `scripts/sample_import.csv`. Expenses in a CSV are signed amounts (negative means money out).

## Tests

```powershell
python -m pytest --cov=policy --cov-fail-under=90
```

Tests use an in-memory database and a scripted model. They do not call the network. Security cases print a pass/fail summary and cover prompt injection, limit changes, duplicate execution, approval expiry, and account-number masking.

## Known limitations

- One seeded user and no login.
- USD only. The simulator and budget are informational, not regulated advice.
- Chat needs a free-model key. Everything else is deterministic.
- Approvals expire 15 minutes after they are created, including the seeded phone-bill card. Run `python scripts/seed.py` to file a fresh one.

## Third-party licenses

| Library | License |
| --- | --- |
| FastAPI | MIT |
| Uvicorn | BSD-3-Clause |
| SQLAlchemy | MIT |
| Pydantic | MIT |
| OpenAI Python SDK | Apache-2.0 |
| pytest | MIT |
| React | MIT |
| React Router | MIT |
| Vite | MIT |
| Tailwind CSS | MIT |
| Recharts | MIT |

Seed data is synthetic and written for this project.
