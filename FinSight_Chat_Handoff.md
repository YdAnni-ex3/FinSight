# FinSight — Chat Handoff & Continuity Summary

> Paste this into a new chat to continue seamlessly. It captures the full state
> of the FinSight project: what it is, what's live, every account/resource, the
> architecture, key commands, hard-won gotchas, and where to pick up.
>
> _Snapshot date: 2026-07-07. Live commit is always visible at the backend
> `/readyz` (`git_sha`)._

---

## 1. What FinSight is

**FinSight — Personal Finance Statement Analyzer & Anomaly Monitor.** A
multi-cloud interview-portfolio project: upload a bank/credit-card statement →
it parses, redacts PII, categorizes, detects anomalies (rules + ML), stores to a
warehouse, and answers natural-language questions via a tool-using agent. Built
offline-first (works with zero cloud), then progressively activated as accounts
were added.

**Goal:** a permanently-live, low/zero-cost demo link that showcases breadth
(Azure + AWS + Snowflake + Databricks + Pinecone + Vercel + Grafana + CI/CD + ML).

## 2. Live URLs

| What | URL |
|---|---|
| Frontend (show this to interviewers) | https://finsight-woad-beta.vercel.app |
| Backend API | https://finsight-gateway.icymeadow-7a1423f4.centralindia.azurecontainerapps.io |
| API readiness (shows live provider + git_sha) | `…/readyz` |
| Prometheus metrics | `…/metrics` |
| Grafana Cloud | https://pluckyrug3487.grafana.net |

## 3. Accounts & resource identifiers (NOT secrets)

- **GitHub:** `YdAnni-ex3/FinSight`. Image: `ghcr.io/ydanni-ex3/finsight-gateway` (public).
- **Azure:** subscription `10916e02-e6e6-4784-9faa-ee33a9239883`, resource group `finsight-rg`, region **Central India** (+ **East US 2** for OpenAI).
  - Storage `finsight10916e` (container `raw-statements`) · Key Vault `finsight-kv-10916e`
  - Azure OpenAI `finsight-openai-10916e` — deployments `chat` = gpt-5-mini, `embeddings` = text-embedding-3-small, api-version `2024-10-21`
  - Container App `finsight-gateway` in env `finsight-env` · Function `finsight-digest-10916e`
  - Deploy service principal `finsight-gh-deploy` (appId `56931758-0e19-4c39-ae80-bc12464ef7d8`)
- **Snowflake:** account `pcuhido-fq35609`, user `yaniket3e`, warehouse `COMPUTE_WH`, database `FINSIGHT`, schemas `ANALYTICS` (live app writes) + `MEDALLION` (Databricks batch).
- **Databricks:** Free Edition `dbc-43a254fa-3d06.cloud.databricks.com`, Unity Catalog `finsight` (bronze/silver/gold), secret scope `finsight`.
- **Pinecone:** index `finsight` (region `us-east-1`).
- **Vercel:** project `finsight-woad-beta`.
- **Grafana Cloud:** stack `pluckyrug3487` (region ap-south-1); metrics via Alloy remote_write.
- **AWS:** IAM user `finsight-bedrock`; Bedrock chat `us.amazon.nova-lite-v1:0` in `us-east-1`; embeddings default `amazon.titan-embed-text-v2:0`.
- **Discord:** webhook configured for the weekly digest.

> 🔒 **Secrets** (Azure OpenAI key, Pinecone key, Snowflake password, AWS keys,
> Discord webhook, Databricks PAT, SP client secret) live **only** in local
> `.env` (gitignored) and Azure Container App secrets. **Never commit them.**

## 4. Architecture & stack

```
User → Vercel (Next.js) → Azure Container Apps (FastAPI gateway, scale-to-zero 0..2)
  ├─ LLM provider abstraction → Azure OpenAI (gpt-5-mini)  ⇄  AWS Bedrock (Nova Lite)   [FINSIGHT_LLM_PROVIDER]
  ├─ Embeddings → Azure OpenAI text-embedding-3-small
  ├─ RAG → Pinecone
  ├─ Warehouse → Snowflake (star schema; live ANALYTICS writes)
  ├─ Anomaly ML → scikit-learn IsolationForest (in image), tracked in MLflow
  └─ Metrics → /metrics → Grafana Alloy → Grafana Cloud
Databricks (bronze→silver→gold) → write_pandas → Snowflake FINSIGHT.MEDALLION
Azure Function (timer, Mon 09:00 UTC) → spend+anomaly digest → Discord (+ warms app & Pinecone)
GitHub Actions → lint/test → build image (GHCR) → auto-deploy to Container Apps
```

## 5. Repo layout (key files)

- `libs/finsight_common/` — shared library: `config.py` (pydantic settings, `FINSIGHT_` prefix), `models.py`, `parsing.py`, `pii.py` (regex redactor), `categorize.py`, `llm_categorize.py`, `analytics.py`, `anomaly.py` (rules + ML + `combine_anomalies`), `rag.py`, `vectorstore.py`, `embeddings.py`, `warehouse.py` (Snowflake store), `agent.py` (ReAct + fallback), `llm/` (`base.py`, `factory.py`, `azure_openai.py`, `bedrock.py`), `ml/` (`features.py`, `anomaly_model.py`).
- `services/gateway/` — FastAPI `app.py`, `metrics.py`, `Dockerfile`.
- `services/digest/` — Azure Function (`function_app.py`, `host.json`, `requirements.txt`).
- `databricks/notebooks/` — `01_bronze_ingest.py`, `02_silver_clean.py`, `03_gold_star.py`.
- `snowflake/ddl/star_schema.sql` · `observability/` (prometheus, grafana, alloy) · `frontend/` (Next.js).
- `scripts/` — `generate_synthetic_statements.py`, `train_anomaly_model.py` (+`--kaggle-csv`, `--kaggle-daily-csv`), `deploy_containerapp.ps1`, `smoke_live.ps1`, `run_alloy.ps1`, `verify_bedrock.py`, `setup_databricks_secrets.ps1`, `provision_azure.ps1`.
- `tests/` — 77 tests. `docs/WELL_ARCHITECTED_REVIEW.md`.

## 6. What's built & live

Parse/PII/categorize · RAG (Pinecone) · anomaly rules **+ IsolationForest ML
trained on 21,550 real Kaggle txns** (India credit-card + Daily Household) with
MLflow · tool-using agent (Azure **and** Bedrock, verified live) · Snowflake
persistence · Databricks medallion → Snowflake · Container Apps + Vercel live ·
Prometheus + Grafana Cloud · Azure Function weekly digest → Discord ·
GitHub Actions CI + auto-deploy (push-to-`main` ships to prod) · git_sha
traceability in `/readyz` · Well-Architected review.

## 7. Deploy flow

`git push origin main` → `.github/workflows/build-image.yml` builds the image to
GHCR (~2 min) and the `deploy` job runs `az containerapp update` (uses the
`AZURE_CREDENTIALS` repo secret). Verify with `/readyz` (git_sha) or
`./scripts/smoke_live.ps1`. Manual deploy: `./scripts/deploy_containerapp.ps1`.

## 8. Key commands (Windows / PowerShell)

```powershell
# deps (no pii extra — presidio breaks the uv venv)
python -m uv sync --extra dev --extra data --extra ai --extra snowflake --extra aws --extra ml --extra mlops --extra obs
python -m uv run ruff check . ; python -m uv run pytest        # lint + 77 tests
python -m uv run python scripts/train_anomaly_model.py --kaggle-csv "data/kaggle/Credit card transactions - India - Simple.csv" --kaggle-daily-csv "data/kaggle/Daily Household Transactions.csv"
./scripts/run_alloy.ps1            # ship live metrics to Grafana Cloud (needs .env creds)
python -m uv run python scripts/verify_bedrock.py   # smoke-test Bedrock from .env
# az needs a PATH refresh first:
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
```

## 9. Gotchas (learned the hard way)

- **uv:** not on PATH → always `python -m uv …`. `uv pip install` targets system Python (fails) → use `uv pip install --python .venv…` or `uv run --with <pkg>`.
- **No local Docker / no func Core Tools** → build images in GitHub Actions; deploy Functions via `az` zip-deploy.
- **PowerShell 5.1 `Compress-Archive` writes BACKSLASH zip paths → invalid on Linux** (Functions host silently indexes 0 functions). Build zips with Python `zipfile` + `arcname=…as_posix()`.
- **Azure Functions Python v2** needs app setting `AzureWebJobsFeatureFlags=EnableWorkerIndexing`. Verify via ARM `…/functions?api-version=2022-03-01` (host `function list` false-negatives on scale-to-zero).
- **New Azure subscription** → register providers: `Microsoft.Web`, `Microsoft.Insights`, `Microsoft.App`, `Microsoft.CognitiveServices`, etc. (`az provider register --namespace … --wait`).
- **`--extra pii`** pulls presidio→spaCy which shells out to pip (absent in uv venv) → import crash. Don't install it; the regex redactor is the real path.
- **Small LLMs (Nova Lite) emit slightly invalid JSON** → the agent must parse defensively and fall back deterministically (done).
- **git push** shows a red "exit code 1" but succeeds (check the `-> main` line). `az` writes warnings to stderr (harmless).
- **MLflow 3.x** rejects the bare file store → use `sqlite:///mlflow.db`; pass `pip_requirements` to avoid pip-based env capture.

## 10. Security to-dos (P0)

- **Rotate** anything shown in chat during setup: Databricks PAT, Azure SP client secret, storage account key. (`az ad sp credential reset --id 56931758-0e19-4c39-ae80-bc12464ef7d8` for the SP.)
- **Add API auth + rate limiting** to the public gateway (currently open).

## 11. Where to continue

Open items (see `FinSight_Status_and_Roadmap.md` for detail): API auth + rate
limiting (P0), Azure budget alerts, Terraform (Mode B IaC), staging environment,
Databricks orchestration, App Insights on the Function, frontend redesign, and a
"understand any finance slip" OCR/multimodal feature. Bedrock is live; Kafka/AKS
remain demo-mode by design.
