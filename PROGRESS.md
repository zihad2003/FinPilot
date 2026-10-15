# FinPilot build tracker

Last updated: 2026-10-16 (Dhaka)

Source of truth for scope: [Agentic Personal Finance Assistant Project Pack.md](./Agentic%20Personal%20Finance%20Assistant%20Project%20Pack.md)

Repo: https://github.com/zihad2003/FinPilot

---

## Status summary

| Area | Status |
| --- | --- |
| Core MVP (8 features) | Done |
| Approval Inbox + policy tiers T0–T3 | Done |
| What-if simulator | Done |
| Security tests + demo evidence script | Done |
| React UI (dashboard, chat, inbox, settings, audit) | Done |
| Live LLM chat (OpenAI-compatible / Gemini) | Done (needs valid key + quota) |
| Section 5 extras (risk score, sub cleaner, etc.) | Not started |
| Sprint 5 docs (technical + security self-assessment) | Not started |
| Demo video + pitch deck | Not started |

---

## Core MVP features

| # | Feature | Status | Notes |
| --- | --- | --- | --- |
| 1 | Transaction ingestion | Done | 6 months seed + CSV import (`POST /transactions/import`) |
| 2 | Auto-categorization | Done | Rules first, LLM fallback, confidence + source; user corrections reused |
| 3 | Smart budget | Done | 50/30/20 baseline adjusted by 3-month averages; budget vs actual |
| 4 | Bill analysis | Done | Recurring detection; price hike + duplicate flags |
| 5 | Spending insights | Done | Chat cites transaction ids; dashboard anomalies |
| 6 | Bill scheduling | Done | Sandbox pay via policy; T2 Approval Inbox |
| 7 | Goal transfers | Done | Goals + T3 auto within per-action/daily caps |
| 8 | Anomaly alerts | Done | Unusual charges, duplicates, price hikes, budget overrun flags |

**Standout:** Approval Inbox — propose / approve / edit / reject, expected effect, policy rule, 15-minute expiry.

---

## Functional requirements (SRS 3.3)

| ID | Requirement | Status |
| --- | --- | --- |
| FR-01 | Seed + CSV import | Done |
| FR-02 | Categorize with confidence + source | Done |
| FR-03 | User category correction remembered | Done |
| FR-04 | Monthly budget + vs actual | Done |
| FR-05 | Recurring payments list | Done |
| FR-06 | Price hike / duplicate / unused subs | Partial — hike + duplicate strong; unused-subscription cleaner not a full feature |
| FR-07 | Chat with cited transactions | Done |
| FR-08 | Action proposal cards | Done |
| FR-09 | Execute approved sandbox actions | Done |
| FR-10 | Savings goals + suggested weekly | Done |
| FR-11 | Anomaly + budget projected alerts | Partial — alerts exist; not a full 30-day cash forecast |
| FR-12 | Permission tier per action type | Done |
| FR-13 | Append-only audit log + CSV export | Done |
| FR-14 | What-if simulator | Done |
| FR-15 | Dashboard (balance, spend, budget, goals, actions) | Done |

---

## Policy and security (SRS 3.4)

| ID | Requirement | Status |
| --- | --- | --- |
| SR-01 | Policy engine outside LLM | Done |
| SR-02 | ALLOW / REQUIRE_APPROVAL / DENY | Done |
| SR-03 | Per-action + daily limits + payee allowlist | Done |
| SR-04 | T2 approval + 15 min expiry | Done |
| SR-05 | Idempotency keys | Done |
| SR-06 | PII masking before LLM | Done |
| SR-07 | Prompt-injection treated as data | Done (tests in `tests/security/`) |
| SR-08 | Minimum tool set per request | Done |
| SR-09 | Secrets in env only | Done |
| SR-10 | Sandbox / not regulated advice banner | Done |

---

## UI pages

| Page | Status |
| --- | --- |
| Dashboard | Done |
| Chat | Done |
| Approval Inbox | Done |
| What-if | Done |
| Settings (tiers / limits) | Done |
| Audit Log + CSV export | Done |

---

## Tests and evidence

| Item | Status |
| --- | --- |
| API / policy / categorize / insights / agent tests | Done |
| Security adversarial tests + summary table | Done |
| Policy engine coverage ≥ 90% | Done (~99% when last run) |
| `scripts/demo_run.py` → `docs/evidence/` | Done |
| Sample evidence: `docs/evidence/demo-20261015T190527Z.json` | Done |

---

## Stack and ops

| Item | Status |
| --- | --- |
| FastAPI + SQLAlchemy + SQLite | Done |
| React + Vite + Tailwind + Recharts | Done |
| Docker Compose | Done |
| README (English setup) | Done |
| `.env` for `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | Done |
| Gemini OpenAI-compat + thought_signature round-trip | Done |
| Pushed to GitHub `zihad2003/FinPilot` | Done |

**Local run**

- API: `python -m uvicorn app.main:app --app-dir backend --port 8000`
- UI: `cd frontend && npm run dev` → http://localhost:5173
- Seed: `python scripts/seed.py`
- Tests: `python -m pytest --cov=policy --cov-fail-under=90`

**Persona:** international student, $1200 allowance, fixed seed (messy merchants, Netflix hike/duplicate, injection string in cafe note).

---

## Not done yet (track next)

### High priority for submission (Sprint 5)

- [ ] `docs/technical_documentation.md`
- [ ] `docs/security_self_assessment.md`
- [ ] Demo video (≤ 5 min)
- [ ] Pitch deck (≤ 10 min talk)
- [ ] Clean-clone test + resubmit evidence log

### Planned innovation extras (from gap plan — not built)

- [ ] Risk score (Low / Medium / High) on every proposal card
- [ ] Subscription cleaner → cancel proposal (no money move)

### Pack Section 5 extras (optional — pick at most 2–3 total)

- [ ] Kill switch / cool-down
- [ ] Tamper-evident audit chain
- [ ] Paycheck splitter
- [ ] Multi-currency view
- [ ] Agent-to-agent auditor
- [ ] Voice / quick-reply chips
- [ ] Weekly coach report
- [ ] Evaluation harness

### Known light gaps

- Automatic round-up *rules* (transfers work; scheduled round-ups are thin)
- Dedicated “unused subscription” product flow
- Full 30-day overdraft / cash-crunch forecast
- Login / multi-user (intentionally single seeded user)

---

## Change log (high level)

| When | What |
| --- | --- |
| 2026-10-16 | Initial MVP: sandbox bank, policy, agent, insights, UI, security tests, what-if, README, Docker |
| 2026-10-16 | Pushed to GitHub |
| 2026-10-16 | Gemini chat fixes: SQLite `.env`, model name, thought_signature preservation, 2026 date hint in system prompt |
| 2026-10-16 | This tracker file created |

---

## How to update this file

When you finish a feature or doc:

1. Flip its checkbox / Status cell to **Done**.
2. Add a row under **Change log**.
3. Keep Section 5 extras unchecked unless you actually ship them before the Oct 20 deadline.
