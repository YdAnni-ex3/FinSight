# FinSight — Status & Roadmap

Covers: (A) status vs. the master checklist, (B) prioritized future work,
(C) a detailed frontend redesign plan, and (D) a spec for the "understand any
finance slip" feature. _Updated 2026-07-07._

Legend: ✅ Done · 🟡 Partial/in-progress · ⬜ Remaining · ➖ N/A / optional

---

## A. Status vs. `FinSight_StepByStep_Execution_Checklist.md`

| # | Item | Status | Notes |
|---|------|:---:|------|
| **P1** | Decisions (email, regions, Kafka posture, card) | ✅ | Azure = Central India + East US 2; Snowflake `pcuhido-fq35609`; Kafka = demo-mode |
| 2.1 | GitHub repo + 2FA | ✅ | Branch protection on `main` still ⬜ |
| 2.2 | Kaggle + `kaggle.json` | ✅ | Used to train the model (2 datasets) |
| 2.3 | Azure account + CLI | ✅ | |
| 2.4 | **AWS account** | ✅ | Done — Bedrock live |
| 2.5 | Snowflake + auto-suspend | ✅ | |
| 2.6 | Databricks Free Edition | ✅ | Medallion ran |
| 2.7 | Pinecone | ✅ | Index `finsight` |
| 2.8 | Vercel | ✅ | Frontend live |
| 2.9 | Grafana Cloud | ✅ | Stack `pluckyrug3487` |
| 2.10 | Docker Hub | ➖ | Used GHCR |
| 3.1 | Azure budget alerts | ⬜ | Recommended (~₹1,500) |
| 3.2 | AWS budget alerts | 🟡 | Set a $5–10 budget when creating the AWS account |
| 3.4 | Resource tagging | 🟡 | Most resources tagged `project=finsight` |
| 4.1–4.3 | RG + Storage + Key Vault | ✅ | |
| 4.4–4.5 | Azure OpenAI + 2 deployments | ✅ | gpt-5-mini + text-embedding-3-small |
| 4.6 | Bedrock model access | ✅ | Auto-enabled (page retired); Nova Lite |
| 4.7 | AWS IAM user | ✅ | `finsight-bedrock` |
| 4.8 | Secrets → Key Vault | 🟡 | KV exists; runtime uses Container App secrets/.env |
| 5.1 | Repo + compose + synthetic + Kaggle | ✅ | |
| 5.2 | Databricks external location → Blob | 🟡 | Ran from uploaded CSVs |
| 5.3–5.4 | UC schemas + Snowflake star + DBX→SF | ✅ | MEDALLION 27/10/103 |
| 5.5 | Categorization → LLM | ✅ | Azure or Bedrock |
| 5.6 | Pinecone index + round-trip | ✅ | |
| 5.7 | **AWS Bedrock invoke** | ✅ | Verified live (`/readyz` = bedrock) |
| 5.8 | MLflow / anomaly ML | 🟡 | Local MLflow (sqlite); no Azure ML workspace |
| 5.9 | SageMaker parallel deploy | ➖ | Optional |
| 5.10 | Kafka/streaming | 🟡 | Redpanda in compose (demo-mode) |
| 5.11–5.12 | Container Apps + Vercel | ✅ | |
| 5.13 | Azure Function timer digest | ✅ | `finsight-digest-10916e` → Discord |
| 5.14 | Terraform (Mode B / AKS) | ⬜ | Not started |
| 5.15–5.16 | CI/CD (secrets + build→deploy) | ✅ | Verified end-to-end |
| 5.17 | Grafana dashboards | ✅ | |
| 5.18 | **Well-Architected review** | ✅ | `docs/WELL_ARCHITECTED_REVIEW.md` |
| 6.1–6.2 | Scale-to-zero + Vercel→API | ✅ | |
| 6.3 | Full E2E (upload→DBX→SF→query) | 🟡 | Live path ✅; Databricks batch is manual |
| 6.4 | Pinecone heartbeat | ✅ | Digest function warms it |
| 6.5 | Custom domain | ➖ | Optional |
| 7.1 | No secrets in committed files | ✅ | Rotate secrets exposed in setup chat |
| 7.2 | Scoped AWS IAM + root MFA | 🟡 | IAM user scoped-ish (FullAccess → tighten); confirm root MFA |
| 7.3 | PII redaction before LLM/Pinecone | ✅ | Regex redactor |
| 7.4 | UC column policies on PII | ⬜ | |
| 7.5 | Network review (Container Apps/KV) | ⬜ | |
| **P8** | Ongoing maintenance habits | ➖ | Your routine |

**Headline:** the entire *core build* — live multi-cloud app, real-data ML,
medallion analytics, CI/CD, observability, scheduled digest — is **done**. The
remaining work is **hardening** (security/IaC/budgets) and **new features**
(sections C & D below).

---

## B. Future roadmap (prioritized)

### P0 — security (do first)
1. **Rotate** the secrets shown during setup: Databricks PAT, Azure SP client secret, storage account key.
2. **API authentication + rate limiting** on the gateway (an API key header + slowapi/Redis token bucket). Today the endpoints are open.

### P1 — hardening & reproducibility
3. **Azure budget alerts** (50/80/100%) + confirm AWS budget.
4. **Terraform (Mode B IaC)** — codify RG, Container Apps, Key Vault, OpenAI, Function, Storage. `terraform plan`-validated; keep AKS/Kafka apply-on-demand.
5. **Key Vault via managed identity** — have the Container App pull secrets from KV instead of env/secretrefs.
6. **Scope the Bedrock IAM policy** to `bedrock:InvokeModel`/`Converse` (drop FullAccess); enable root MFA.
7. **SLOs + Grafana alert rules**; add **Application Insights** to the Function for log visibility + failure alerts.

### P2 — operations & performance
8. **Staging revision + automated rollback**; add a **post-deploy smoke test** (`smoke_live.ps1`) as a CI step.
9. **Orchestrate Databricks** (Databricks Jobs or ADF) so the medallion runs on a schedule/trigger instead of manually; wire an external location to Blob `raw-statements` for true upload→lakehouse→warehouse E2E.
10. **Agent perf**: snapshot the transaction store once per run (currently N reads/run); add analytics response caching.
11. **Unity Catalog PII column policies**; network review of Container Apps/KV.

### Feature-level (bigger bets)
12. **"Understand any finance slip"** — OCR/multimodal ingestion (see section D). High wow-factor.
13. **Frontend redesign** (see section C).
14. **Custom domain** on Vercel; **multi-user auth** (per-user statements) via Azure AD B2C / Clerk.
15. **Budgeting & forecasting** — monthly budgets, trend/forecast (Prophet or a small model), "you'll overspend on dining" nudges.
16. **Streaming path** (Kafka/Redpanda + a consumer) for real-time transaction ingestion — currently demo-mode.
17. **SageMaker parallel deploy** of the anomaly model — the multi-cloud ML flex.
18. **Evaluation harness** for the agent (golden Q&A set, regression scoring across Azure vs Bedrock).

---

## C. Frontend redesign plan (do later — not yet implemented)

**Problem:** the current `frontend/app/page.tsx` is a single utilitarian page
(upload → text summary + plain bars + a Q&A box). It works but looks plain.

**Goal:** a polished, interactive, visual dashboard that impresses in a demo.

### Design system
- Keep **Next.js (App Router) + TailwindCSS**; add **shadcn/ui** (Radix-based components), **lucide-react** (icons), **Recharts** (charts), **Framer Motion** (animations).
- Define a palette (finance-trust blues/greens + accent), typography scale, spacing, and **dark mode** (next-themes). Consistent rounded cards, soft shadows, subtle gradients.

### Layout & components
1. **Hero / landing** — headline, one-line value prop, an illustration (e.g. undraw.co "finance"/"data" SVGs), and a prominent **drag-and-drop upload** zone with file preview and a "Try sample statement" button (demo mode).
2. **Summary cards row** — animated stat cards: Total Inflow, Total Outflow, Net, #Transactions, #Anomalies (count-up animation, trend arrows, category icons).
3. **Spend-by-category** — a **donut chart** + a ranked list with a per-category **icon** and color; hover tooltips; click to filter.
4. **Anomalies panel** — severity-colored **alert cards** (high=red, medium=amber) with an icon, the message, and the offending transaction(s); "Review" affordance.
5. **Transactions table** — sortable/filterable (TanStack Table), category chips, search, PII shown redacted.
6. **Agent chat panel** — a modern chat UI: message bubbles, **streaming** tokens, **tool-call badges** ("used total_spend"), suggested prompts, and a small "powered by Azure OpenAI / AWS Bedrock" indicator pulled from `/readyz` (`llm_provider`).
7. **Polish** — loading **skeletons**, empty states with illustrations, toasts for errors, responsive/mobile layout, a favicon/logo, and a footer linking the Grafana dashboard + GitHub.

### Nice-to-haves
- A tiny **architecture diagram** page ("How it works") — great for interviews.
- **Framer Motion** page/section transitions; number count-ups; chart enter animations.
- **Optimistic UI** while the backend cold-starts (skeletons + "waking the service…").

### Effort
~1–2 focused sessions. No backend changes required (the API already returns
`summary`, `by_category`, `anomalies`, and the agent `answer` + `steps`). Add a
tiny call to `/readyz` to show the active LLM.

---

## D. Feature: "Understand any finance slip" (OCR / multimodal — spec only)

**Vision:** the user drops in **any** finance artifact — a **restaurant bill
photo, a handwritten calculation, a monthly-expenses report (PDF/image), a UPI
screenshot** — and FinSight extracts structured transactions and runs them
through the same categorize → redact → anomaly → store → Q&A pipeline.

### Approach (recommended: hybrid)
1. **Structured docs (printed receipts/invoices):** **Azure AI Document
   Intelligence** prebuilt **receipt/invoice** models → high-accuracy structured
   fields (merchant, date, line items, totals, tax). Best precision, low prompt risk.
2. **Freeform / handwritten / screenshots:** a **multimodal LLM** — Azure OpenAI
   **gpt-4o/gpt-5 vision** or **AWS Bedrock** (Claude 3.5 / Nova, which are
   multimodal). Send the image with a strict prompt: *"Extract every line item as
   JSON: {date, description, amount, currency, category}. If handwritten, do your
   best; mark low-confidence items."* This handles messy/handwritten inputs the
   OCR model can't.
3. **Router:** try Document Intelligence first for image/PDF that looks like a
   receipt; fall back to the multimodal LLM for everything else (or run both and
   merge). Keep it behind the existing **provider abstraction** so it works on
   Azure or Bedrock.

### Architecture / implementation plan
- **New endpoint** `POST /api/slips/ingest` accepting `image/*` and `application/pdf`.
- **Pipeline:** upload → (Doc Intelligence | vision LLM) → normalize to the existing
  `Statement` / `Transaction[]` model → **reuse** the current `_process_upload`
  downstream (PII redaction → categorize → anomaly → index → store). Minimal new code
  because everything after extraction already exists.
- **New module** `libs/finsight_common/vision.py` with a `SlipExtractor` interface
  and two implementations (`DocIntelligenceExtractor`, `VisionLLMExtractor`), chosen
  via settings — mirroring the `llm/` factory pattern.
- **Config:** `FINSIGHT_DOC_INTELLIGENCE_ENDPOINT/KEY`, `FINSIGHT_VISION_MODEL`
  (e.g. `gpt-4o` or a Bedrock multimodal id). Offline/dev fallback: a stub that
  returns a fixed parse so tests stay hermetic.
- **Frontend:** the same drag-and-drop zone accepts images; show a **preview +
  extracted line items for confirmation/editing** before saving (handwriting is
  imperfect — let the user correct low-confidence rows). This "human-in-the-loop"
  step is itself a great demo talking point.

### Hard parts & mitigations
- **Handwriting accuracy** → confirmation UI + confidence flags; prefer vision LLM.
- **Amounts/currency ambiguity** → validate numbers, default currency INR, sanity-check totals against summed line items.
- **PII in images** (names, card numbers) → run the existing redaction on extracted
  text; consider redacting before any LLM sees it (for printed docs, redact
  post-OCR; for vision LLM, note the image itself goes to the model — call this out).
- **Cost/latency** → cache by file hash; Doc Intelligence first (cheaper/faster for
  receipts) and vision LLM only when needed.

### Phased delivery
1. **MVP:** printed receipt → Document Intelligence → transactions (reuse pipeline).
2. **V2:** vision-LLM path for handwritten/freeform + the confirmation UI.
3. **V3:** monthly-report PDFs (multi-page, tables) + auto-reconciliation against
   existing statements (dedupe).

**Why it's compelling:** it turns FinSight from "upload a bank CSV" into "photograph
anything financial and it just works" — a memorable, multimodal, human-in-the-loop
AI feature that also reuses ~80% of the existing backend.
