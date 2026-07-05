"""FinSight weekly digest — Azure Functions (timer trigger).

Runs on a schedule, asks the live gateway for a spend summary + anomalies, and
delivers a short digest. The same call exercises the LLM/agent + Pinecone path,
which doubles as the "heartbeat" that keeps the Container App warm and the
Pinecone Starter index from going idle (checklist 6.4).

Lean by design: only httpx + azure-functions, no heavy finsight_common imports —
it talks to the deployed API over HTTP.
"""

from __future__ import annotations

import logging
import os

import azure.functions as func
import httpx

app = func.FunctionApp()

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8000").rstrip("/")
WEBHOOK_URL = os.environ.get("DIGEST_WEBHOOK_URL", "")
TIMEOUT = float(os.environ.get("DIGEST_TIMEOUT_SECONDS", "60"))


def format_digest(by_category: dict[str, float], summary: str) -> str:
    """Render the digest text from a spend breakdown + an agent summary."""
    lines = ["FinSight — weekly digest", ""]
    if summary:
        lines += [summary, ""]
    if by_category:
        lines.append("Spend by category:")
        for category, amount in list(by_category.items())[:8]:
            lines.append(f"  - {category}: {amount:,.0f}")
    else:
        lines.append("No transactions on record yet.")
    return "\n".join(lines)


def build_digest() -> str:
    """Fetch analytics + an agent summary from the gateway and format a digest."""
    with httpx.Client(timeout=TIMEOUT) as client:
        spend = client.get(f"{GATEWAY_URL}/api/analytics/spend")
        spend.raise_for_status()
        by_category = spend.json().get("by_category", {})

        agent = client.post(
            f"{GATEWAY_URL}/api/agent",
            json={
                "question": (
                    "Give me a concise weekly summary of my spending and flag any anomalies."
                )
            },
        )
        agent.raise_for_status()
        summary = agent.json().get("answer", "")

    return format_digest(by_category, summary)


def deliver(digest: str) -> None:
    """Log the digest and, if a webhook is configured, POST it (Slack/Discord)."""
    logging.info("finsight.digest\n%s", digest)
    if not WEBHOOK_URL:
        return
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            client.post(WEBHOOK_URL, json={"content": digest, "text": digest})
    except httpx.HTTPError as exc:
        logging.warning("digest webhook delivery failed: %s", exc)


@app.timer_trigger(
    schedule="0 0 9 * * 1",  # Mondays 09:00 UTC
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def weekly_digest(timer: func.TimerRequest) -> None:
    """Build and deliver the weekly digest (also warms the API + Pinecone)."""
    if timer.past_due:
        logging.warning("weekly_digest timer is past due")
    try:
        deliver(build_digest())
    except httpx.HTTPError as exc:
        logging.error("weekly_digest failed to reach the gateway: %s", exc)
