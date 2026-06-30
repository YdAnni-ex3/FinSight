"use client";

import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Txn = {
  txn_date: string;
  description: string;
  amount: number;
  category: string | null;
};

type ParseResponse = {
  summary: {
    transaction_count: number;
    total_inflow: number;
    total_outflow: number;
    net: number;
  };
  statement: { transactions: Txn[] };
};

const inr = (n: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(n);

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ParseResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const res = await fetch(`${API_URL}/api/statements/parse`, { method: "POST", body });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail ?? `Request failed (${res.status})`);
      }
      setResult((await res.json()) as ParseResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-3xl font-bold">FinSight</h1>
      <p className="mt-1 text-slate-600">
        Personal Finance Statement Analyzer &amp; Anomaly Monitor
      </p>

      <form
        onSubmit={onSubmit}
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

      {error && (
        <p className="mt-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
      )}

      {result && (
        <section className="mt-8">
          <div className="grid grid-cols-3 gap-4">
            <Stat label="Inflow" value={inr(result.summary.total_inflow)} />
            <Stat label="Outflow" value={inr(result.summary.total_outflow)} />
            <Stat label="Net" value={inr(result.summary.net)} />
          </div>

          <table className="mt-6 w-full overflow-hidden rounded-lg border border-slate-200 bg-white text-sm">
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
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs">
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
