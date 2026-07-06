"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useTheme } from "next-themes";
import {
  BarChart3,
  Camera,
  FileText,
  TrendingUp,
  TrendingDown,
  Wallet,
  AlertTriangle,
  MessageCircle,
  Send,
  Moon,
  Sun,
  UtensilsCrossed,
  Car,
  ShoppingCart,
  Zap,
  Plane,
  Heart,
  ShoppingBag,
  Music,
  CircleDot,
  CheckCircle,
  RefreshCw,
  ArrowRight,
  Sparkles,
  X,
  Activity,
  GitFork,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Types ──────────────────────────────────────────────────────────────────────

type Txn = { txn_date: string; description: string; amount: number; category: string | null };

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
    source?: string;
    extractor?: string;
  };
  statement: { transactions: Txn[] };
  by_category: Record<string, number>;
  anomalies: Anomaly[];
};

type ChatMsg = { role: "user" | "ai"; content: string; tools?: string[] };

// ── Category palette ──────────────────────────────────────────────────────────

const CAT: Record<string, { color: string; Icon: React.ElementType }> = {
  dining:        { color: "#F97316", Icon: UtensilsCrossed },
  groceries:     { color: "#22C55E", Icon: ShoppingCart },
  transport:     { color: "#3B82F6", Icon: Car },
  entertainment: { color: "#A855F7", Icon: Music },
  utilities:     { color: "#EAB308", Icon: Zap },
  travel:        { color: "#06B6D4", Icon: Plane },
  healthcare:    { color: "#EF4444", Icon: Heart },
  shopping:      { color: "#EC4899", Icon: ShoppingBag },
  income:        { color: "#10B981", Icon: TrendingUp },
  other:         { color: "#94A3B8", Icon: CircleDot },
};
const COLORS = Object.values(CAT).map((c) => c.color);

const inr = (n: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(Math.abs(n));

const isImage = (name: string) => /\.(jpe?g|png|webp|gif|bmp|heic)$/i.test(name);

// ── Donut chart (pure SVG — no recharts needed) ───────────────────────────────

function DonutChart({ data }: { data: { name: string; value: number }[] }) {
  const total = data.reduce((s, c) => s + c.value, 0);
  if (!total) return null;
  const cx = 72, cy = 72, r = 52, inner = 36;
  const toRad = (d: number) => (d * Math.PI) / 180;
  let angle = -90;
  const paths = data.map((item, i) => {
    const slice = (item.value / total) * 360;
    const end = angle + slice;
    const x1 = cx + r * Math.cos(toRad(angle));
    const y1 = cy + r * Math.sin(toRad(angle));
    const x2 = cx + r * Math.cos(toRad(end));
    const y2 = cy + r * Math.sin(toRad(end));
    const x3 = cx + inner * Math.cos(toRad(end));
    const y3 = cy + inner * Math.sin(toRad(end));
    const x4 = cx + inner * Math.cos(toRad(angle));
    const y4 = cy + inner * Math.sin(toRad(angle));
    const large = slice > 180 ? 1 : 0;
    const d = `M${x1},${y1} A${r},${r} 0 ${large},1 ${x2},${y2} L${x3},${y3} A${inner},${inner} 0 ${large},0 ${x4},${y4}Z`;
    angle = end;
    return <path key={item.name} d={d} fill={COLORS[i % COLORS.length]} />;
  });
  return (
    <div className="relative w-36 h-36 shrink-0">
      <svg viewBox="0 0 144 144" className="w-full h-full drop-shadow-sm">{paths}</svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <span className="text-2xl font-bold text-slate-900 dark:text-white">{data.length}</span>
        <span className="text-[10px] uppercase tracking-widest text-slate-500">categories</span>
      </div>
    </div>
  );
}

// ── Stat card ──────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, color, Icon }: {
  label: string; value: string; sub?: string; color: string; Icon: React.ElementType;
}) {
  return (
    <div className="flex-1 min-w-0 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-4 shadow-sm hover:shadow-md transition-all duration-200 animate-slide-up">
      <div className="flex items-center gap-2 mb-2">
        <div className="p-1.5 rounded-xl" style={{ backgroundColor: color + "22" }}>
          <Icon size={14} style={{ color }} />
        </div>
        <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-widest">{label}</span>
      </div>
      <div className="text-xl font-bold text-slate-900 dark:text-white tabular-nums truncate">{value}</div>
      {sub && <div className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">{sub}</div>}
    </div>
  );
}

// ── Main ────────────────────────────────────────────────────────────────────────

export default function Home() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"overview" | "transactions" | "chat">("overview");
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [sortCol, setSortCol] = useState<"date" | "amount">("date");
  const [sortDir, setSortDir] = useState<1 | -1>(1);
  const [catFilter, setCatFilter] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => setMounted(true), []);
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  const handleFile = useCallback((f: File) => {
    setFile(f);
    setResult(null);
    setError(null);
    setCatFilter(null);
    if (isImage(f.name)) {
      const url = URL.createObjectURL(f);
      setPreview(url);
    } else {
      setPreview(null);
    }
  }, []);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, [handleFile]);

  async function analyze() {
    if (!file) return;
    setLoading(true);
    setError(null);
    const endpoint = isImage(file.name) ? `${API_URL}/api/slips/ingest` : `${API_URL}/api/statements/analyze`;
    try {
      const body = new FormData();
      body.append("file", file);
      const res = await fetch(endpoint, { method: "POST", body });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail ?? `Request failed (${res.status})`);
      }
      setResult(await res.json());
      setTab("overview");
      setMsgs([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  async function onChat(e: React.FormEvent) {
    e.preventDefault();
    if (!chatInput.trim() || chatLoading) return;
    const q = chatInput.trim();
    setChatInput("");
    setMsgs((p) => [...p, { role: "user", content: q }]);
    setChatLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/agent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const data = await res.json();
      setMsgs((p) => [...p, {
        role: "ai",
        content: data.answer ?? "No answer.",
        tools: Array.isArray(data.steps) ? data.steps.map((s: { tool: string }) => s.tool) : [],
      }]);
    } catch {
      setMsgs((p) => [...p, { role: "ai", content: "Something went wrong." }]);
    } finally {
      setChatLoading(false);
    }
  }

  const byCat = result ? Object.entries(result.by_category).sort(([, a], [, b]) => b - a) : [];
  const maxCat = byCat[0]?.[1] ?? 1;
  const txns = result?.statement.transactions ?? [];
  const filtered = catFilter ? txns.filter((t) => t.category === catFilter) : txns;
  const sorted = [...filtered].sort((a, b) =>
    sortDir * (sortCol === "date" ? a.txn_date.localeCompare(b.txn_date) : a.amount - b.amount)
  );

  if (!mounted) return null;

  // ── UPLOAD VIEW ─────────────────────────────────────────────────────────────
  const uploadView = (
    <div className="flex flex-col items-center py-8 animate-fade-in">
      {/* Hero */}
      <div className="text-center mb-10">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 text-sm font-medium mb-6 border border-indigo-100 dark:border-indigo-900">
          <Sparkles size={14} /> AI-Powered Finance Intelligence
        </div>
        <h1 className="text-5xl sm:text-6xl font-extrabold tracking-tight text-slate-900 dark:text-white mb-4 leading-[1.1]">
          Understand your<br />
          <span className="bg-gradient-to-r from-blue-500 via-violet-500 to-purple-600 bg-clip-text text-transparent">
            finances
          </span>
        </h1>
        <p className="text-lg text-slate-500 dark:text-slate-400 max-w-lg mx-auto leading-relaxed">
          Drop a bank statement <em>or photograph any finance slip</em> — restaurant bill,
          handwritten calculation, UPI screenshot — and get instant AI insights.
        </p>
      </div>

      {/* Upload card */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !file && fileRef.current?.click()}
        className={`w-full max-w-xl rounded-3xl border-2 border-dashed transition-all duration-300 cursor-pointer select-none
          ${dragging
            ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950/30 scale-[1.01]"
            : "border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800/40 hover:border-indigo-400 dark:hover:border-indigo-600 hover:bg-indigo-50/40 dark:hover:bg-indigo-950/20"
          }`}
      >
        <div className="p-8">
          {preview ? (
            /* Image slip preview */
            <div className="flex flex-col items-center gap-4">
              <div className="relative">
                <img
                  src={preview}
                  alt="Finance slip"
                  className="max-h-52 max-w-full rounded-xl border border-slate-200 dark:border-slate-700 shadow-lg object-contain"
                />
                <button
                  onClick={(e) => { e.stopPropagation(); setFile(null); setPreview(null); }}
                  className="absolute -top-2 -right-2 bg-rose-500 hover:bg-rose-600 text-white rounded-full p-1.5 transition-colors shadow-md"
                >
                  <X size={12} />
                </button>
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">{file?.name}</p>
                <p className="text-xs text-indigo-600 dark:text-indigo-400 mt-1">
                  📸 Finance slip detected — AI will extract transactions
                </p>
              </div>
            </div>
          ) : file ? (
            /* Statement file selected */
            <div className="flex flex-col items-center gap-3">
              <div className="w-16 h-16 rounded-2xl bg-emerald-50 dark:bg-emerald-950/30 flex items-center justify-center">
                <FileText size={32} className="text-emerald-600 dark:text-emerald-400" />
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">{file.name}</p>
                <p className="text-xs text-slate-400 mt-1">Ready to analyze</p>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); setFile(null); }}
                className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 underline"
              >
                Remove
              </button>
            </div>
          ) : (
            /* Empty drop zone */
            <div className="flex flex-col items-center gap-5">
              {/* Illustrated icon cluster */}
              <div className="flex items-end gap-2">
                <div className="w-14 h-14 rounded-2xl bg-blue-50 dark:bg-blue-950/40 border border-blue-100 dark:border-blue-900 flex items-center justify-center shadow-sm">
                  <FileText size={28} className="text-blue-500" />
                </div>
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-50 to-violet-50 dark:from-indigo-950/40 dark:to-violet-950/40 border border-indigo-100 dark:border-indigo-900 flex items-center justify-center shadow-md -mb-1">
                  <Camera size={30} className="text-indigo-500" />
                </div>
                <div className="w-14 h-14 rounded-2xl bg-violet-50 dark:bg-violet-950/40 border border-violet-100 dark:border-violet-900 flex items-center justify-center shadow-sm">
                  <BarChart3 size={28} className="text-violet-500" />
                </div>
              </div>
              <div className="text-center">
                <p className="text-base font-semibold text-slate-700 dark:text-slate-300">
                  Drag & drop your file here
                </p>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                  Bank statements <span className="text-slate-300 dark:text-slate-600">·</span> Finance photos{" "}
                  <span className="text-slate-300 dark:text-slate-600">·</span> Receipts
                </p>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); fileRef.current?.click(); }}
                className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold transition-colors shadow-sm hover:shadow-md"
              >
                Choose File
              </button>
              <p className="text-xs text-slate-400">CSV · XLSX · PDF · JPG · PNG · WEBP — up to 10 MB</p>
            </div>
          )}
        </div>
      </div>

      <input
        ref={fileRef}
        type="file"
        accept=".csv,.xlsx,.xls,.pdf,.jpg,.jpeg,.png,.webp,.gif,.bmp,.heic"
        className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); e.target.value = ""; }}
      />

      {error && (
        <div className="mt-4 flex items-start gap-2.5 max-w-xl w-full rounded-2xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900 px-4 py-3 animate-fade-in">
          <AlertTriangle size={16} className="text-rose-500 mt-0.5 shrink-0" />
          <p className="text-sm text-rose-700 dark:text-rose-400">{error}</p>
        </div>
      )}

      {file && (
        <button
          onClick={analyze}
          disabled={loading}
          className="mt-6 flex items-center gap-2.5 px-8 py-3.5 rounded-2xl bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700 text-white font-semibold text-base shadow-lg hover:shadow-xl transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <><RefreshCw size={18} className="animate-spin" /> Analyzing…</>
          ) : (
            <>
              <Sparkles size={18} />
              {isImage(file.name) ? "Extract & Analyze Slip" : "Analyze Statement"}
              <ArrowRight size={18} />
            </>
          )}
        </button>
      )}

      {/* Feature pills */}
      <div className="flex flex-wrap justify-center gap-2 mt-10 max-w-lg">
        {[
          { icon: "🤖", label: "AI Categorization" },
          { icon: "⚠️", label: "Anomaly Detection" },
          { icon: "📸", label: "OCR Slip Reading" },
          { icon: "💬", label: "Natural Language Q&A" },
          { icon: "🔒", label: "PII Redaction" },
          { icon: "☁️", label: "Multi-Cloud (Azure + AWS)" },
        ].map(({ icon, label }) => (
          <span
            key={label}
            className="text-xs px-3 py-1.5 rounded-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 shadow-sm"
          >
            {icon} {label}
          </span>
        ))}
      </div>
    </div>
  );

  // ── DASHBOARD VIEW ──────────────────────────────────────────────────────────
  const dashboardView = result && (
    <div className="space-y-5 animate-fade-in">
      {/* Slip source badge */}
      {result.summary.source === "slip" && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-violet-50 dark:bg-violet-950/30 border border-violet-200 dark:border-violet-900 text-violet-700 dark:text-violet-400 text-sm font-medium w-fit">
          <Camera size={14} />
          Extracted from finance slip via {result.summary.extractor ?? "vision LLM"} · {result.summary.transaction_count} transaction{result.summary.transaction_count !== 1 ? "s" : ""} found
        </div>
      )}

      {/* Stat row */}
      <div className="flex gap-3 overflow-x-auto pb-1 -mx-1 px-1">
        <StatCard label="Inflow" value={inr(result.summary.total_inflow)} sub="credits" color="#10B981" Icon={TrendingUp} />
        <StatCard label="Outflow" value={inr(result.summary.total_outflow)} sub="debits" color="#EF4444" Icon={TrendingDown} />
        <StatCard
          label="Net"
          value={(result.summary.net >= 0 ? "+" : "−") + inr(result.summary.net)}
          sub={result.summary.net >= 0 ? "surplus" : "deficit"}
          color={result.summary.net >= 0 ? "#10B981" : "#EF4444"}
          Icon={Wallet}
        />
        <StatCard label="Transactions" value={String(result.summary.transaction_count)} sub={`via ${result.summary.categorizer}`} color="#6366F1" Icon={Activity} />
        <StatCard
          label="Anomalies"
          value={String(result.summary.anomaly_count)}
          sub={result.summary.anomaly_count > 0 ? "needs review" : "all clear"}
          color={result.summary.anomaly_count > 0 ? "#F59E0B" : "#10B981"}
          Icon={AlertTriangle}
        />
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 p-1 rounded-xl bg-slate-100 dark:bg-slate-800 w-fit">
        {(["overview", "transactions", "chat"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 capitalize
              ${tab === t
                ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm"
                : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
              }`}
          >
            {t === "chat" ? "Ask AI" : t === "overview" ? "Overview" : "Transactions"}
          </button>
        ))}
      </div>

      {/* ── OVERVIEW ── */}
      {tab === "overview" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 animate-fade-in">
          {/* Category chart */}
          <div className="card p-6">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-white mb-5 uppercase tracking-wide">Spend by Category</h2>
            <div className="flex items-center gap-6">
              <DonutChart data={byCat.map(([name, value]) => ({ name, value }))} />
              <div className="flex-1 space-y-2 min-w-0">
                {byCat.map(([cat, amt], i) => {
                  const meta = CAT[cat] ?? CAT.other;
                  const { Icon } = meta;
                  const color = COLORS[i % COLORS.length];
                  const isActive = !catFilter || catFilter === cat;
                  return (
                    <button
                      key={cat}
                      onClick={() => { setCatFilter(catFilter === cat ? null : cat); setTab("transactions"); }}
                      className={`w-full flex items-center gap-2 group transition-opacity ${isActive ? "" : "opacity-30"}`}
                    >
                      <div className="p-1 rounded shrink-0" style={{ backgroundColor: color + "22" }}>
                        <Icon size={11} style={{ color }} />
                      </div>
                      <span className="text-xs text-slate-600 dark:text-slate-400 capitalize w-20 truncate text-left">{cat}</span>
                      <div className="flex-1 h-1.5 rounded-full bg-slate-100 dark:bg-slate-700 overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-700"
                          style={{ width: `${(amt / maxCat) * 100}%`, backgroundColor: color }}
                        />
                      </div>
                      <span className="text-[11px] tabular-nums text-slate-500 dark:text-slate-400 w-20 text-right shrink-0">{inr(amt)}</span>
                    </button>
                  );
                })}
              </div>
            </div>
            <p className="text-[11px] text-slate-400 mt-4">Click a category to filter transactions</p>
          </div>

          {/* Anomalies */}
          <div className="card p-6">
            <div className="flex items-center gap-2 mb-4">
              <h2 className="text-sm font-semibold text-slate-900 dark:text-white uppercase tracking-wide">Anomalies</h2>
              {result.anomalies.length > 0 && (
                <span className="ml-auto text-xs font-medium px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
                  {result.anomalies.length} detected
                </span>
              )}
            </div>
            {result.anomalies.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-40 gap-2">
                <div className="w-12 h-12 rounded-full bg-emerald-50 dark:bg-emerald-950/30 flex items-center justify-center">
                  <CheckCircle size={24} className="text-emerald-500" />
                </div>
                <p className="text-sm font-semibold text-emerald-700 dark:text-emerald-400">All clear!</p>
                <p className="text-xs text-slate-400">No anomalies detected in this statement</p>
              </div>
            ) : (
              <div className="space-y-3">
                {result.anomalies.map((a, i) => (
                  <div
                    key={i}
                    className={`rounded-xl p-3.5 border text-sm ${
                      a.severity === "high"
                        ? "bg-rose-50 dark:bg-rose-950/20 border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-400"
                        : a.severity === "medium"
                        ? "bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-900 text-amber-700 dark:text-amber-400"
                        : "bg-slate-50 dark:bg-slate-700/30 border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300"
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                      <div>
                        <span className="font-semibold text-xs uppercase tracking-wide block mb-0.5 opacity-70">{a.severity}</span>
                        <p className="text-xs leading-relaxed">{a.message}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── TRANSACTIONS ── */}
      {tab === "transactions" && (
        <div className="card overflow-hidden animate-fade-in">
          {catFilter && (
            <div className="px-4 py-2.5 bg-indigo-50 dark:bg-indigo-950/30 border-b border-indigo-100 dark:border-indigo-900 flex items-center justify-between">
              <span className="text-xs text-indigo-700 dark:text-indigo-400">
                Filtered: <strong className="capitalize">{catFilter}</strong> — {filtered.length} of {txns.length} transactions
              </span>
              <button onClick={() => setCatFilter(null)} className="text-xs text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-200 flex items-center gap-1">
                <X size={10} /> Clear
              </button>
            </div>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 dark:bg-slate-700/50 border-b border-slate-200 dark:border-slate-700">
                <tr>
                  <th
                    onClick={() => { setSortDir(sortCol === "date" ? (sortDir * -1) as 1 | -1 : 1); setSortCol("date"); }}
                    className="text-left px-4 py-3 text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-widest cursor-pointer hover:text-slate-700 dark:hover:text-slate-200 select-none"
                  >
                    Date {sortCol === "date" ? (sortDir > 0 ? "↑" : "↓") : ""}
                  </th>
                  <th className="text-left px-4 py-3 text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-widest">Description</th>
                  <th className="text-left px-4 py-3 text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-widest">Category</th>
                  <th
                    onClick={() => { setSortDir(sortCol === "amount" ? (sortDir * -1) as 1 | -1 : 1); setSortCol("amount"); }}
                    className="text-right px-4 py-3 text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-widest cursor-pointer hover:text-slate-700 dark:hover:text-slate-200 select-none"
                  >
                    Amount {sortCol === "amount" ? (sortDir > 0 ? "↑" : "↓") : ""}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700/50">
                {sorted.map((t, i) => {
                  const catMeta = CAT[t.category ?? "other"] ?? CAT.other;
                  const color = COLORS[Object.keys(CAT).indexOf(t.category ?? "other") % COLORS.length] ?? "#94A3B8";
                  const { Icon } = catMeta;
                  return (
                    <tr key={i} className="hover:bg-slate-50 dark:hover:bg-slate-700/20 transition-colors">
                      <td className="px-4 py-3 text-slate-500 dark:text-slate-400 text-xs whitespace-nowrap font-mono">{t.txn_date}</td>
                      <td className="px-4 py-3 text-slate-700 dark:text-slate-300 max-w-xs truncate text-sm">{t.description}</td>
                      <td className="px-4 py-3">
                        {t.category && (
                          <button
                            onClick={() => { setCatFilter(t.category!); }}
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold hover:opacity-80 transition-opacity"
                            style={{ backgroundColor: color + "20", color }}
                          >
                            <Icon size={9} />
                            {t.category}
                          </button>
                        )}
                      </td>
                      <td className={`px-4 py-3 text-right font-semibold tabular-nums text-sm ${t.amount < 0 ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"}`}>
                        {t.amount < 0 ? "−" : "+"}{inr(t.amount)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── CHAT ── */}
      {tab === "chat" && (
        <div className="card overflow-hidden animate-fade-in">
          <div className="flex flex-col h-[500px]">
            {/* Messages area */}
            <div className="flex-1 overflow-y-auto p-5 space-y-3">
              {msgs.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center gap-4">
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center shadow-lg">
                    <MessageCircle size={30} className="text-white" />
                  </div>
                  <div>
                    <p className="font-semibold text-slate-900 dark:text-white text-base">Ask me about your finances</p>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">I have full context of your statement</p>
                  </div>
                  <div className="flex flex-wrap gap-2 justify-center max-w-sm mt-2">
                    {[
                      "How much did I spend on dining?",
                      "Which category costs the most?",
                      "Are there any unusual transactions?",
                      "What's my monthly net balance?",
                    ].map((q) => (
                      <button
                        key={q}
                        onClick={() => setChatInput(q)}
                        className="text-xs px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors text-left border border-transparent hover:border-indigo-100 dark:hover:border-indigo-900"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                msgs.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div
                      className={`max-w-xs lg:max-w-md rounded-2xl px-4 py-2.5 text-sm leading-relaxed
                        ${msg.role === "user"
                          ? "bg-gradient-to-br from-blue-600 to-violet-600 text-white rounded-br-none"
                          : "bg-slate-100 dark:bg-slate-700 text-slate-800 dark:text-slate-200 rounded-bl-none"
                        }`}
                    >
                      {msg.content}
                      {msg.tools && msg.tools.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2 pt-2 border-t border-white/10 dark:border-slate-600">
                          {msg.tools.map((tool, j) => (
                            <span key={j} className="text-[10px] px-1.5 py-0.5 rounded bg-black/10 dark:bg-white/10 font-mono">
                              ⚙ {tool}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
              {chatLoading && (
                <div className="flex justify-start">
                  <div className="bg-slate-100 dark:bg-slate-700 rounded-2xl rounded-bl-none px-4 py-3">
                    <div className="flex gap-1">
                      {[0, 150, 300].map((d) => (
                        <div key={d} className="w-1.5 h-1.5 rounded-full bg-slate-400 dark:bg-slate-500 animate-bounce" style={{ animationDelay: `${d}ms` }} />
                      ))}
                    </div>
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Input */}
            <div className="border-t border-slate-200 dark:border-slate-700 p-3.5">
              <form onSubmit={onChat} className="flex gap-2">
                <input
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Ask about your spending…"
                  className="flex-1 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700/50 px-4 py-2.5 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
                <button
                  type="submit"
                  disabled={chatLoading || !chatInput.trim()}
                  className="p-2.5 rounded-xl bg-gradient-to-br from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700 text-white disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm hover:shadow-md"
                >
                  <Send size={18} />
                </button>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  // ── SHELL ────────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 transition-colors duration-300">
      {/* Header */}
      <header className="sticky top-0 z-30 glass border-b border-slate-200 dark:border-slate-800">
        <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center shadow-sm">
              <BarChart3 size={20} className="text-white" />
            </div>
            <div>
              <span className="text-lg font-extrabold text-slate-900 dark:text-white">FinSight</span>
              <span className="hidden sm:inline text-xs text-slate-400 dark:text-slate-500 ml-2">AI Finance Analyzer</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {result && (
              <button
                onClick={() => { setResult(null); setFile(null); setPreview(null); setCatFilter(null); }}
                className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 px-3 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                <RefreshCw size={13} /> New
              </button>
            )}
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400 transition-colors"
            >
              <GitFork size={18} />
            </a>
            <button
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition-colors"
              aria-label="Toggle theme"
            >
              {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
            </button>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-5xl mx-auto px-6 py-8">
        {result ? dashboardView : uploadView}
      </main>

      {/* Footer */}
      <footer className="mt-16 border-t border-slate-200 dark:border-slate-800 py-6">
        <div className="max-w-5xl mx-auto px-6 flex flex-wrap gap-3 items-center justify-between text-xs text-slate-400 dark:text-slate-500">
          <span>© 2025 FinSight · Azure OpenAI · AWS Bedrock · Pinecone · Snowflake · Databricks</span>
          <div className="flex gap-4">
            <span>Grafana Metrics</span>
            <span>MLflow Experiments</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
