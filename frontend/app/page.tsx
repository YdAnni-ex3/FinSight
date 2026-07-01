"use client";

import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Txn = {
  txn_date: string;
  description: string;
  amount: number;
  category: string | null;
};

type Anomaly = {
  type: string;
  severity: string;
  message: string;
  transactions: { date: string; description: string; amount: number }[];
};

type AnalyzeResponse = {
  summary: {
    transaction_count: number;
    total_inflow: number;
    total_outflow: number;
    net: number;
    categorizer: string;
    anomaly_count: number;
  };
  statement: { transactions: Txn[] };
  by_category: Record<string, number>;
  anomalies: Anomaly[];
};

const inr = (n: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(n);

const severityStyle: Record<string, string> = {
  high: "border-red-200 bg-red-50 text-red-800",
  medium: "border-amber-200 bg-amber-50 text-amber-800",
  low: "border-slate-200 bg-slate-50 text-slate-700",
};

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [question, setQuestion] = useState("How much did I spend on food?");
  const [answer, setAnswer] = useState<string | null>(null);
  const [steps, setSteps] = useState<{ tool: string }[]>([]);
  const [asking, setAsking] = useState(false);

  async function onAnalyze(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setAnswer(null);
    setSteps([]);
    try {
      const body = new FormData();
      body.append("file", file);
      const res = await fetch(`${API_URL}/api/statements/analyze`, { method: "POST", body });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail ?? `Request failed (${res.status})`);
      }
      setResult((await res.json()) as AnalyzeResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  async function onAsk(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setAsking(true);
    setAnswer(null);
    setSteps([]);
    try {
      const res = await fetch(`${API_URL}/api/agent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await res.json();
      setAnswer(data.answer ?? "No answer.");
      setSteps(Array.isArray(data.steps) ? data.steps : []);
    } catch {
      setAnswer("Something went wrong.");
    } finally {
      setAsking(false);
    }
  }

  const maxCat = result ? Math.max(1, ...Object.values(result.by_category)) : 1;

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-3xl font-bold">FinSight</h1>
      <p className="mt-1 text-slate-600">
        Personal Finance Statement Analyzer &amp; Anomaly Monitor
      </p>

      <form
        onSubmit={onAnalyze}
        className="mt-8 flex items-center gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
      >
        <input
          type="file"
          accept=".csv,.xlsx,.xls,.pdf"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="flex-1 text-sm"
        />
        <button
          type="submit"
          disabled={!file || loading}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          {loading ? "Analyzing…" : "Analyze"}
        </button>
      </form>

      {error && <p className="mt-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}

      {result && (
        <div className="mt-8 space-y-8">
          <section>
            <div className="grid grid-cols-3 gap-4">
              <Stat label="Inflow" value={inr(result.summary.total_inflow)} />
              <Stat label="Outflow" value={inr(result.summary.total_outflow)} />
              <Stat label="Net" value={inr(result.summary.net)} />
            </div>
            <p className="mt-2 text-xs text-slate-500">
              {result.summary.transaction_count} transactions · categorized by{" "}
              <span className="font-medium">{result.summary.categorizer}</span> ·{" "}
              {result.summary.anomaly_count} anomal
              {result.summary.anomaly_count === 1 ? "y" : "ies"}
            </p>
          </section>

          {result.anomalies.length > 0 && (
            <section>
              <h2 className="mb-3 text-lg font-semibold">Anomalies</h2>
              <div className="space-y-2">
                {result.anomalies.map((a, i) => (
                  <div
                    key={i}
                    className={`rounded-md border px-4 py-3 text-sm ${severityStyle[a.severity] ?? severityStyle.low}`}
                  >
                    <span className="mr-2 rounded-full bg-white/60 px-2 py-0.5 text-xs font-medium uppercase">
                      {a.severity}
                    </span>
                    {a.message}
                  </div>
                ))}
              </div>
            </section>
          )}

          <section>
            <h2 className="mb-3 text-lg font-semibold">Spend by category</h2>
            <div className="space-y-2">
              {Object.entries(result.by_category).map(([cat, amount]) => (
                <div key={cat} className="flex items-center gap-3 text-sm">
                  <div className="w-28 shrink-0 capitalize text-slate-600">{cat}</div>
                  <div className="h-4 flex-1 rounded bg-slate-100">
                    <div
                      className="h-4 rounded bg-slate-800"
                      style={{ width: `${(amount / maxCat) * 100}%` }}
                    />
                  </div>
                  <div className="w-24 shrink-0 text-right tabular-nums">{inr(amount)}</div>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold">Ask about your money</h2>
            <form onSubmit={onAsk} className="flex gap-2">
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="e.g. How much did I spend on food?"
                className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
              <button
                type="submit"
                disabled={asking}
                className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
              >
                {asking ? "Asking…" : "Ask"}
              </button>
            </form>
            {answer && (
              <div className="mt-3 rounded-md border border-slate-200 bg-white px-4 py-3 text-sm">
                <p>{answer}</p>
                {steps.length > 0 && (
                  <div className="mt-2 flex flex-wrap items-center gap-1 text-xs text-slate-500">
                    <span>tools:</span>
                    {steps.map((s, i) => (
                      <span
                        key={i}
                        className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-slate-600"
                      >
                        {s.tool}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold">Transactions</h2>
            <table className="w-full overflow-hidden rounded-lg border border-slate-200 bg-white text-sm">
              <thead className="bg-slate-100 text-left text-slate-600">
                <tr>
                  <th className="px-3 py-2">Date</th>
                  <th className="px-3 py-2">Description</th>
                  <th className="px-3 py-2">Category</th>
                  <th className="px-3 py-2 text-right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {result.statement.transactions.map((t, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    <td className="px-3 py-2 whitespace-nowrap">{t.txn_date}</td>
                    <td className="px-3 py-2">{t.description}</td>
                    <td className="px-3 py-2">
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs capitalize">
                        {t.category ?? "—"}
                      </span>
                    </td>
                    <td
                      className={`px-3 py-2 text-right tabular-nums ${
                        t.amount < 0 ? "text-red-600" : "text-emerald-700"
                      }`}
                    >
                      {inr(t.amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      )}
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-lg font-semibold tabular-nums">{value}</div>
    </div>
  );
}
