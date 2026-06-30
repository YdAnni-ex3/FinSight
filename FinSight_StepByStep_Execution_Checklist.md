# FinSight — Master Step-by-Step Execution Checklist
### Every step, in order, to go from zero accounts to a permanently live demo link

> This is the granular walk-through version of `FinSight_Setup_Cost_Deployment_Plan.md`. Work top to bottom. Don't skip ahead — several steps (budget alerts, Snowflake auto-suspend) need to exist *before* the steps that follow them. Check items off as you go.

---

## PART 1 — Decisions to make before you register anything

These five decisions affect which signup options you choose below, so settle them first.

- [ ] **1.1** Confirm whether you have any valid academic email (current or alumni) tied to your CS degree. This determines whether you use Azure for Students ($100, no card, 12 months) or the standard Azure Free Account ($200, card required, 30 days) in Part 2. You only get one Azure free account per person ever, so pick deliberately.
- [ ] **1.2** Pick your primary Azure region. Recommendation: **Central India** (lowest latency for you) — but first check that Microsoft Foundry / Azure OpenAI model deployments are actually available there (availability varies by region and changes over time; check in the Azure OpenAI model availability docs when you reach Part 4). If your preferred model isn't available in Central India, fall back to **Southeast Asia** or a region your bank/card has no issue billing in.
- [ ] **1.3** Pick your Snowflake cloud + region at signup time — this **cannot be changed later** without creating a new trial account. Recommendation: same cloud as your primary Azure work (Azure) and a region geographically close to India, to minimize cross-cloud data transfer friction later when you connect it to Databricks/ADF.
- [ ] **1.4** Decide your Kafka/AKS posture up front (Section 2.4 of the cost plan): demo-mode default (spin up only for build/demo sessions — recommended), small persistent footprint, or fully budgeted always-on. Write this decision down — you'll reference it in Part 6.
- [ ] **1.5** Confirm your card has international/online transactions enabled (log into net banking or your card's app and toggle this on now) — this is the #1 cause of failed Azure/AWS signups for Indian users, and you'll need it working for steps in Part 2.

---

## PART 2 — Account registration, in exact order

### 2.1 GitHub
- [ ] Create/confirm your GitHub account, enable 2FA.
- [ ] Create a new repository named `finsight` (private is fine to start; you can open-source it later for the portfolio).
- [ ] Add a `README.md` with a one-paragraph project description (you'll flesh this out later) and a `.gitignore` for Python/Node.
- [ ] Set up branch protection on `main`: Settings → Branches → require pull request before merging.

### 2.2 Kaggle
- [ ] Create your Kaggle account.
- [ ] Go to Account Settings → API → "Create New Token" → this downloads `kaggle.json`.
- [ ] Save `kaggle.json` somewhere safe locally (you'll use it with the `kaggle` CLI in Phase 0 of the build plan to pull the datasets listed in that document).

### 2.3 Azure
- [ ] If eligible per step 1.1, go to the Azure for Students signup page and sign up with your academic email — no card needed. **Skip to 2.3.6.**
- [ ] If not eligible: go to azure.microsoft.com/free → "Start free."
- [ ] Sign in with a Microsoft account (create one if needed, or use your GitHub account where offered).
- [ ] Enter phone number for verification (OTP).
- [ ] Enter card details — note this is a verification hold (commonly ~$1 equivalent), not a charge.
- [ ] Agree to terms, complete signup — you land in the Azure portal with $200 credit active for 30 days.
- [ ] **2.3.6** Once in the portal: go to **Subscriptions** → confirm you're on the Free Trial/Student subscription → note your Subscription ID somewhere (you'll need it constantly for CLI commands and Terraform).
- [ ] Install the Azure CLI locally (`az` command) and run `az login` to confirm it connects to your account.

### 2.4 AWS
- [ ] Go to aws.amazon.com/free → "Create an AWS account."
- [ ] Enter email, account name, password.
- [ ] At the plan-selection step, choose the **Free Plan** explicitly (not Paid) — this caps what can ever be charged until you deliberately upgrade.
- [ ] Complete identity verification (phone + card, same international-transactions note as above).
- [ ] Once in the console, go to **Billing → Credits** and confirm your credit balance and expiration date are visible (mark that expiration date in your calendar now — see Part 1.4 logic, roughly 5–6 months out).
- [ ] Install the AWS CLI locally and run `aws configure` with an access key you generate from IAM (don't use root credentials for daily work — see Part 7 security step).

### 2.5 Snowflake
- [ ] Go to the Snowflake trial signup page.
- [ ] Fill in name, email, company name (use your own name as a placeholder if signing up as an individual).
- [ ] Choose your cloud provider and region per your Part 1.3 decision — **double-check before submitting, this can't be changed**.
- [ ] Choose **Standard edition** (not Enterprise — you don't need multi-cluster warehouses or extended Time Travel for this project, and Standard is cheaper per credit if you continue past the trial).
- [ ] Check your email, click the verification link.
- [ ] Log in to Snowsight, and **immediately** go to Admin → Warehouses → your default warehouse → set **Auto-Suspend = 60 seconds**, **Auto-Resume = ON**. Do this before running a single query.
- [ ] Save your account identifier (shown in the URL / under your profile, format like `orgname-accountname`) — you'll need this for every external tool connection (Databricks, ADF, your FastAPI services).
- [ ] Note the trial end date; set a calendar reminder for day 25.

### 2.6 Databricks — Free Edition
- [ ] Go to the Databricks Free Edition signup page specifically (not the 14-day trial flow — that one expires; Free Edition does not).
- [ ] Sign up with email, no card required.
- [ ] Once in the workspace, go to Catalog and confirm Unity Catalog is enabled by default (it is, on Free Edition).
- [ ] Create a new Notebook, run a trivial cell (`print("hello")`) just to confirm the serverless compute spins up correctly.

### 2.7 Pinecone
- [ ] Sign up at pinecone.io, no card required for Starter.
- [ ] Create your first project.
- [ ] Note: any index you create on Starter is locked to the `us-east-1` AWS region — this is fine, just remember it when you're troubleshooting latency later.
- [ ] Generate an API key (Project → API Keys) and store it securely (you'll put this in Key Vault/GitHub secrets later, never in code).

### 2.8 Vercel
- [ ] Sign up at vercel.com using your GitHub account (this auto-links them, which makes deployment trivial later).
- [ ] No project to create yet — you'll do this in Part 6 once the frontend exists.

### 2.9 Grafana Cloud
- [ ] Sign up at grafana.com/auth/sign-up, free tier, no card required.
- [ ] Once in, go to your stack's "Connections" → note your Prometheus remote-write endpoint URL and the API key — save these for Part 6.

### 2.10 Docker Hub
- [ ] Create a free account at hub.docker.com (you'll mainly use Azure Container Registry for the cloud side, but a Docker Hub account is useful for pulling public base images without rate-limit issues).

---

## PART 3 — Budget guardrails (do this before provisioning a single real resource)

### 3.1 Azure budget alerts
- [ ] In the Azure Portal, search "Cost Management + Billing."
- [ ] Go to Budgets → "+ Add."
- [ ] Set scope to your subscription, name it `finsight-monthly-budget`.
- [ ] Set amount to roughly ₹1,500–2,000 (~$20).
- [ ] Add alert conditions at 50%, 80%, and 100% of budget, sent to your email.
- [ ] Separately, check Subscriptions → your subscription → confirm a "credit remaining" indicator is visible; check it weekly.

### 3.2 AWS budget alerts
- [ ] In the AWS Console, go to **Billing and Cost Management → Budgets**.
- [ ] Click "Create budget" → "Use a template (simplified)" → "Monthly cost budget."
- [ ] Set your threshold amount, add your email for alerts.
- [ ] Also check the "Credits" page under Billing to see your exact $200 credit expiration date.

### 3.3 Snowflake monitoring habit
- [ ] No automated alert system needed here — just check the credit balance indicator in the top-right of Snowsight once a week during the trial, and right after any large data-loading session.

### 3.4 Tagging discipline
- [ ] From this point on, every Azure resource you create gets a tag `project:finsight` (you can set a default tag at the resource-group level so it inherits automatically — set this when you create the resource group in Part 4).

---

## PART 4 — Initial cloud resource provisioning

- [ ] **4.1** Create your resource group: via Azure Portal or CLI (`az group create --name finsight-rg --location centralindia --tags project=finsight`). All FinSight Azure resources live here, nowhere else — this makes cost tracking and final teardown trivial.
- [ ] **4.2** Create your Storage Account inside that resource group, with a Blob container named `raw-statements` (this is where uploaded PDFs/XLSX land before processing).
- [ ] **4.3** Create your Azure Key Vault inside the resource group — this is where every API key (Pinecone, Azure OpenAI, AWS, Snowflake) gets stored from now on, never in code or `.env` files committed to GitHub.
- [ ] **4.4** Create your Microsoft Foundry / Azure OpenAI resource inside the resource group, in a region confirmed (per step 1.2) to support the models you need.
- [ ] **4.5** In that Foundry resource, deploy two model endpoints: one chat-completion model (cost-efficient tier, e.g. a mini-class model) and one embeddings model. Note both deployment names — you'll reference them by name in code, not by raw model name.
- [ ] **4.6** In AWS, go to the Bedrock console → "Model access" → request access to the specific foundation model(s) you plan to use for the multi-cloud module. Approval can take a little time for some models — do this now so it's ready by the time you reach that build phase.
- [ ] **4.7** In AWS IAM, create a dedicated IAM user (not root) with programmatic access scoped to just Bedrock + SageMaker permissions for this project; this is what your `aws configure` from step 2.4 should actually use day-to-day.
- [ ] **4.8** Push every secret generated so far (Pinecone API key, Azure OpenAI key, Snowflake credentials, AWS access keys) into Key Vault now, before you write a line of application code.

---

## PART 5 — Build-phase execution checklist (operational side only)

Follow this in lockstep with the 16 build phases in `FinSight_Build_Plan.md`. Each item below is the *account/infra* action that needs to happen at that point — the code itself is covered in that other document.

- [ ] **5.1 (Phase 0–1)** Clone your `finsight` repo locally; set up the local docker-compose stack from the build plan; pull both Kaggle datasets using your `kaggle.json` token; generate your first batch of synthetic statement PDFs/Excel files.
- [ ] **5.2 (Phase 2)** In Databricks Free Edition, set up an external location pointing at your Azure Blob `raw-statements` container (Catalog → External Locations → New) so Databricks can read uploaded files directly.
- [ ] **5.3 (Phase 2)** Create your three Unity Catalog schemas: `finsight.bronze`, `finsight.silver`, `finsight.gold`.
- [ ] **5.4 (Phase 3)** In Snowflake, create your database and the star-schema tables (the DDL is in the build plan). Connect Databricks to Snowflake using a Snowflake connector/partner-connect so the Gold-layer load can run.
- [ ] **5.5 (Phase 4)** Wire your FastAPI categorization service to the Azure OpenAI deployment names from step 4.5, pulling the key from Key Vault (not hardcoded).
- [ ] **5.6 (Phase 5)** Create your first Pinecone index (note the region lock from 2.7); confirm a test upsert + query round-trip works before building the full embedding pipeline.
- [ ] **5.7 (Phase 6)** Set up your AWS Bedrock client using the IAM user from 4.7, confirm a basic invoke call succeeds for the multi-provider LLM abstraction.
- [ ] **5.8 (Phase 7)** Create your Azure ML workspace inside the resource group; self-host MLflow as a small container (locally first, then later as a Container Apps service) rather than paying for managed MLflow.
- [ ] **5.9 (Phase 7, optional)** If doing the SageMaker parallel-deploy module, create a SageMaker domain in AWS now.
- [ ] **5.10 (Phase 8)** Per your Part 1.4 decision: either provision a temporary Kafka setup (local Docker for dev, real broker only during spin-up sessions) or set up the small persistent option you chose.
- [ ] **5.11 (Phase 9–10)** Once your first FastAPI service is containerized, do a first manual deploy to Azure Container Apps to confirm the whole chain (Docker build → ACR push → Container App) works before automating it in CI/CD.
- [ ] **5.12 (Phase 9–10)** Connect your `frontend/` folder in the repo to your Vercel account (Vercel → Add New Project → select the repo → set root directory to `frontend/`) — this gives you your first real shareable URL immediately, well before the backend is finished, which is genuinely useful for iterative demoing.
- [ ] **5.13 (Phase 11)** Create your Azure Function (Timer trigger) for the weekly digest scheduling, in the same resource group.
- [ ] **5.14 (Phase 12–13)** Write the Terraform modules for the full Mode B architecture (resource group, AKS, ACR, Key Vault, Foundry, AI Search, Snowflake provider). Run `terraform plan` against your real subscription to validate it, but hold off on `apply` for AKS specifically until you're ready for a build/demo session (per your Section 2.4 decision).
- [ ] **5.15 (Phase 14)** Set up GitHub Actions secrets: in your repo's Settings → Secrets and variables → Actions, add the Azure service principal credentials, ACR login, and any other keys the pipeline needs (pull these from Key Vault references where possible rather than duplicating raw values into GitHub).
- [ ] **5.16 (Phase 14)** Write the first GitHub Actions workflow: lint/test → build image → push to ACR → deploy to Container Apps on merge to `main`. Confirm it runs green on a trivial change before building anything more complex on top of it.
- [ ] **5.17 (Phase 15)** Point your services' metrics/logging at the Grafana Cloud endpoint from step 2.9; build your first dashboard panel (request latency is a good first one) so you have something to show even before every service is finished.
- [ ] **5.18 (Phase 16)** Go through the Well-Architected Framework self-review once your core build is functionally complete, and write it up as a one-page document — this becomes both a security checkpoint and an interview artifact.

---

## PART 6 — Going live: connecting everything into one permanent link

- [ ] **6.1** Confirm every FastAPI service is deployed to Azure Container Apps with `min replicas = 0` (scale-to-zero) by default.
- [ ] **6.2** Confirm your Vercel frontend's environment variables point at your Container Apps' public URLs (not localhost) — Vercel project Settings → Environment Variables.
- [ ] **6.3** Do one full end-to-end manual test on the live URLs: upload a synthetic statement → confirm it lands in Blob storage → confirm the Databricks job processes it → confirm it appears in Snowflake → confirm a natural-language query against it works end-to-end through the deployed agent orchestrator.
- [ ] **6.4** Set up the Pinecone "heartbeat" query as part of your scheduled Azure Function (a trivial no-op query weekly) so the Starter-plan index never auto-pauses from inactivity.
- [ ] **6.5** (Optional polish) Buy a custom domain, point it at your Vercel deployment via Vercel's domain settings.
- [ ] **6.6** Bookmark your live URL and your Azure/AWS/Snowflake/Pinecone/Grafana dashboards together somewhere (a personal notes doc) so you can do the pre-interview warm-up check (6.7) quickly.
- [ ] **6.7** Before any actual interview or demo: open the live link yourself 10–15 minutes ahead of time, run one query through it to clear cold starts, and pull up your Grafana dashboard and Databricks/Snowflake consoles in separate tabs in case you're asked to show the pipeline running live, not just the frontend.

---

## PART 7 — Security and hygiene pass (do once core build is live, repeat periodically)

- [ ] **7.1** Confirm no API keys, connection strings, or passwords exist in any committed file — search the repo history, not just the current state, since a key committed once and later removed is still in git history (rotate any key that was ever exposed this way).
- [ ] **7.2** Confirm you're using a scoped IAM user for AWS day-to-day work, not root credentials (step 4.7) — and that root has MFA enabled regardless.
- [ ] **7.3** Confirm a real PII-redaction pass happens before any uploaded statement content reaches Azure OpenAI or Pinecone (this should already exist from the build plan's Phase 1 — this is just the verification step).
- [ ] **7.4** Set Unity Catalog access policies on at least the raw/PII-containing columns (build plan Phase 2) — verify this is actually enforced, not just documented.
- [ ] **7.5** Review Container Apps and Key Vault network settings — confirm nothing is more publicly exposed than it needs to be for the demo to work.

---

## PART 8 — Ongoing maintenance (weekly/monthly habits once live)

- [ ] **Weekly**: two-minute check of Azure Cost Analysis and AWS Billing dashboard for anything unexpected.
- [ ] **Weekly**: confirm the Pinecone heartbeat job actually ran (check Pinecone console's last-query timestamp).
- [ ] **Around day 25 of the Snowflake trial**: either finish core warehouse work or add a card to convert to pay-as-you-go (Section 2.3 of the cost plan).
- [ ] **Around month 5 of the AWS free-credit window**: decide whether to upgrade to a paid AWS plan or formally wind the Bedrock/SageMaker module down to "built, documented, and torn down" status for interviews.
- [ ] **Monthly**: confirm GitHub Actions CI/CD is still green on `main` (a stale failing pipeline undermines the "always working" story if anyone checks).
- [ ] **Before each interview**: run the Part 6.7 warm-up check.

---

## What "done" looks like

When every box above is checked, you have: a permanently live link requiring effectively no ongoing cost, a fully documented and reproducible "full architecture" build (Terraform + AKS + Kafka) you can stand up on demand for a deeper demo, working CI/CD that keeps the live version current automatically, and a cost/security story that's a genuine engineering talking point rather than an afterthought. From here, return to `FinSight_Build_Plan.md` for the actual code at each phase.
