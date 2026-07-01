"""A tool-using finance agent (ReAct-style, JSON actions).

The agent reasons over an in-process :class:`TransactionStore` that is filled as
statements are analyzed. Each turn the LLM emits one JSON action: either call a
tool or return a final answer; tool results feed the next turn (bounded loop).
With no LLM configured it falls back to a deterministic keyword router, so it
always works and stays testable offline.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel

from .analytics import spend_by_category
from .anomaly import detect_anomalies
from .llm.base import ChatMessage, LLMProvider
from .models import Category, Statement, Transaction


class TransactionStore:
    """In-process store of analyzed transactions the agent reasons over."""

    def __init__(self) -> None:
        self._transactions: list[Transaction] = []

    def add(self, transactions: list[Transaction]) -> None:
        self._transactions.extend(transactions)

    def all(self) -> list[Transaction]:
        return list(self._transactions)

    def clear(self) -> None:
        self._transactions.clear()

    def __len__(self) -> int:
        return len(self._transactions)


def _view(txn: Transaction) -> dict:
    return {
        "date": txn.txn_date.isoformat(),
        "description": txn.description,
        "amount": float(txn.amount),
        "category": txn.category.value if txn.category else "other",
    }


# ---- Tools: each takes the store plus kwargs and returns a JSON-safe dict ----


def _tool_search_transactions(store: TransactionStore, keywords: str = "", limit: int = 10) -> dict:
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10
    terms = re.findall(r"[a-z0-9]+", str(keywords).lower())
    hits = [
        _view(t)
        for t in store.all()
        if not terms or any(term in t.description.lower() for term in terms)
    ]
    return {"count": len(hits), "transactions": hits[:limit]}


def _tool_total_spend(
    store: TransactionStore,
    category: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> dict:
    total = 0.0
    count = 0
    for txn in store.all():
        if txn.amount >= 0:
            continue
        cat = txn.category.value if txn.category else "other"
        if category and cat != category:
            continue
        iso = txn.txn_date.isoformat()
        if since and iso < since:
            continue
        if until and iso > until:
            continue
        total += float(-txn.amount)
        count += 1
    return {
        "category": category,
        "since": since,
        "until": until,
        "total": round(total, 2),
        "count": count,
    }


def _tool_spend_breakdown(store: TransactionStore) -> dict:
    return {"by_category": spend_by_category(Statement(transactions=store.all()))}


def _tool_list_anomalies(store: TransactionStore) -> dict:
    anomalies = detect_anomalies(Statement(transactions=store.all()))
    return {"count": len(anomalies), "anomalies": [a.model_dump() for a in anomalies]}


_TOOLS: dict[str, dict[str, Any]] = {
    "search_transactions": {
        "fn": _tool_search_transactions,
        "description": "Find transactions whose description matches keywords.",
        "arguments": {"keywords": "space-separated words", "limit": "max results (default 10)"},
    },
    "total_spend": {
        "fn": _tool_total_spend,
        "description": "Total outflow, optionally filtered by category and/or ISO date range.",
        "arguments": {
            "category": "a category or omit for all",
            "since": "ISO date or omit",
            "until": "ISO date or omit",
        },
    },
    "spend_breakdown": {
        "fn": _tool_spend_breakdown,
        "description": "Total spend grouped by category.",
        "arguments": {},
    },
    "list_anomalies": {
        "fn": _tool_list_anomalies,
        "description": "List unusual or duplicate charges.",
        "arguments": {},
    },
}

_CATEGORIES = ", ".join(c.value for c in Category)
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


class AgentStep(BaseModel):
    tool: str
    arguments: dict
    result: dict


class AgentResult(BaseModel):
    answer: str
    steps: list[AgentStep]


def _parse_action(text: str) -> dict | None:
    match = _JSON_OBJECT.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _clean_args(tool: str, args: dict) -> dict:
    allowed = set(_TOOLS[tool]["arguments"].keys())
    return {k: v for k, v in args.items() if k in allowed}


def _system_prompt() -> str:
    lines = [
        "You are FinSight, a personal-finance agent. Use ONLY the tools to answer.",
        f"Categories: {_CATEGORIES}.",
        "",
        "Tools:",
    ]
    for name, spec in _TOOLS.items():
        args = ", ".join(f"{k} ({v})" for k, v in spec["arguments"].items()) or "none"
        lines.append(f"- {name}: {spec['description']} Args: {args}")
    lines += [
        "",
        "Each turn, respond with ONE JSON object and nothing else:",
        '{"action":"tool","tool":"<name>","arguments":{...}}  to call a tool, or',
        '{"action":"answer","answer":"<concise answer>"}  when you have enough info.',
        "Use total_spend/spend_breakdown for amounts and list_anomalies for unusual charges.",
    ]
    return "\n".join(lines)


class FinanceAgent:
    """Bounded ReAct loop over the transaction store, with an offline fallback."""

    def __init__(
        self,
        store: TransactionStore,
        chat: LLMProvider | None = None,
        max_steps: int = 4,
    ) -> None:
        self._store = store
        self._chat = chat
        self._max_steps = max_steps

    def run(self, question: str) -> AgentResult:
        if self._chat is None:
            return self._fallback(question)
        try:
            return self._run_llm(question)
        except Exception:
            return self._fallback(question)

    def _run_llm(self, question: str) -> AgentResult:
        messages = [
            ChatMessage(role="system", content=_system_prompt()),
            ChatMessage(role="user", content=question),
        ]
        steps: list[AgentStep] = []
        for _ in range(self._max_steps):
            raw = self._chat.chat(messages)
            action = _parse_action(raw)
            if not action:
                return AgentResult(answer=raw.strip(), steps=steps)
            if action.get("action") == "answer":
                return AgentResult(answer=str(action.get("answer", "")).strip(), steps=steps)

            tool = action.get("tool")
            args = action.get("arguments") or {}
            if tool not in _TOOLS:
                messages.append(
                    ChatMessage(
                        role="user", content=f"Unknown tool. Choose from: {', '.join(_TOOLS)}."
                    )
                )
                continue

            result = _TOOLS[tool]["fn"](self._store, **_clean_args(tool, args))
            steps.append(AgentStep(tool=tool, arguments=args, result=result))
            messages.append(ChatMessage(role="assistant", content=raw))
            messages.append(
                ChatMessage(role="user", content=f"Observation: {json.dumps(result)[:2000]}")
            )

        final = self._chat.chat(
            [
                *messages,
                ChatMessage(
                    role="user", content="Now answer the original question in one sentence."
                ),
            ]
        )
        return AgentResult(answer=final.strip(), steps=steps)

    def _fallback(self, question: str) -> AgentResult:
        q = question.lower()
        if any(w in q for w in ("anomal", "unusual", "duplicate", "fraud", "suspicious")):
            result = _tool_list_anomalies(self._store)
            answer = f"Found {result['count']} anomal{'y' if result['count'] == 1 else 'ies'}."
            if result["anomalies"]:
                answer += " " + result["anomalies"][0]["message"]
            return AgentResult(
                answer=answer, steps=[AgentStep(tool="list_anomalies", arguments={}, result=result)]
            )

        if any(w in q for w in ("breakdown", "by category", "each category", "categories")):
            result = _tool_spend_breakdown(self._store)
            top = list(result["by_category"].items())[:3]
            answer = (
                ("Top categories: " + ", ".join(f"{k} {v:,.0f}" for k, v in top))
                if top
                else "No spending yet."
            )
            return AgentResult(
                answer=answer,
                steps=[AgentStep(tool="spend_breakdown", arguments={}, result=result)],
            )

        if any(w in q for w in ("how much", "total", "spend", "spent", "cost")):
            category = next((c.value for c in Category if c.value in q), None)
            result = _tool_total_spend(self._store, category=category)
            label = f" on {category}" if category else ""
            answer = (
                f"You spent {result['total']:,.0f}{label} across {result['count']} transactions."
            )
            return AgentResult(
                answer=answer,
                steps=[
                    AgentStep(tool="total_spend", arguments={"category": category}, result=result)
                ],
            )

        result = _tool_search_transactions(self._store, keywords=question)
        answer = f"Found {result['count']} matching transactions."
        return AgentResult(
            answer=answer,
            steps=[
                AgentStep(
                    tool="search_transactions", arguments={"keywords": question}, result=result
                )
            ],
        )
