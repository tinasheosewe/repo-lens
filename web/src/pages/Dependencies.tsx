import { useEffect, useState } from "react";
import { RefreshCw, Flame, Link2, ChevronDown, ChevronRight } from "lucide-react";
import { api } from "../api/client";
import type { Evidence, QueryResult } from "../types";
import ResultPanel from "../components/ResultPanel";

/* ------------------------------------------------------------------ */
/* Tab button                                                          */
/* ------------------------------------------------------------------ */
type Tab = "cycles" | "hotspots" | "coupling";

function TabBtn({
  active,
  label,
  icon: Icon,
  onClick,
}: {
  active: boolean;
  label: string;
  icon: React.ElementType;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-4 py-2 text-xs font-medium rounded-lg transition-all duration-200 ${
        active
          ? "bg-t-primary/15 text-t-primary border border-t-primary/30"
          : "text-gray-500 hover:text-gray-300 border border-transparent"
      }`}
    >
      <Icon size={14} />
      {label}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Cycle visualization                                                 */
/* ------------------------------------------------------------------ */
function CycleCard({ ev }: { ev: Evidence }) {
  const parts = ev.description.split(" → ");
  const [open, setOpen] = useState(false);
  const expandable = !!ev.code_snippet;

  return (
    <div className="glass rounded-xl p-4 hover:border-t-primary/20 transition-colors">
      <button
        type="button"
        onClick={() => expandable && setOpen((value) => !value)}
        disabled={!expandable}
        className={`w-full text-left ${expandable ? "cursor-pointer" : "cursor-default"}`}
      >
        <div className="flex items-start gap-2">
          {expandable && (
            <span className="mt-0.5 text-gray-500 shrink-0">
              {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </span>
          )}
          <div className="flex items-center flex-wrap gap-1.5">
            {parts.map((p, i) => (
              <span key={i} className="flex items-center gap-1.5">
                <span className="text-xs font-mono text-gray-200 bg-gray-800 px-2 py-0.5 rounded">
                  {p}
                </span>
                {i < parts.length - 1 && (
                  <RefreshCw size={10} className="text-amber-400" />
                )}
              </span>
            ))}
          </div>
        </div>
      </button>
      {expandable && open && (
        <div className="mt-4 ml-6 rounded-lg border border-t-border/40 bg-gray-950/50 overflow-hidden">
          <div className="px-4 py-2 text-[11px] uppercase tracking-wider text-gray-500 border-b border-t-border/30">
            Cycle Detail
          </div>
          <pre className="overflow-x-auto px-4 py-3 text-xs leading-6 text-gray-300 font-mono whitespace-pre-wrap">
            {ev.code_snippet}
          </pre>
        </div>
      )}
    </div>
  );
}

function parseHotspotCount(description: string): number {
  const values = [...description.matchAll(/fan-(?:in|out)=(\d+)/g)].map((match) =>
    parseInt(match[1], 10),
  );
  return values.reduce((max, value) => Math.max(max, value), 0);
}

function parseHotspotMetrics(description: string): { fanIn: number; fanOut: number } {
  const fanInMatch = description.match(/fan-in=(\d+)/);
  const fanOutMatch = description.match(/fan-out=(\d+)/);

  return {
    fanIn: fanInMatch ? parseInt(fanInMatch[1], 10) : 0,
    fanOut: fanOutMatch ? parseInt(fanOutMatch[1], 10) : 0,
  };
}

/* ------------------------------------------------------------------ */
/* Hotspot bar                                                         */
/* ------------------------------------------------------------------ */
function HotspotRow({
  ev,
  maxCount,
}: {
  ev: Evidence;
  maxCount: number;
}) {
  const [open, setOpen] = useState(false);
  const count = parseHotspotCount(ev.description);
  const metrics = parseHotspotMetrics(ev.description);
  const pct = maxCount > 0 ? (count / maxCount) * 100 : 20;
  const expandable = !!ev.code_snippet;

  return (
    <div className="hover:bg-white/[0.02] transition-colors">
      <button
        type="button"
        onClick={() => expandable && setOpen((value) => !value)}
        disabled={!expandable}
        className={`w-full py-2.5 px-4 text-left ${expandable ? "cursor-pointer" : "cursor-default"}`}
      >
        <div className="flex items-start gap-2">
          {expandable && (
            <span className="mt-0.5 text-gray-500 shrink-0">
              {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </span>
          )}
          <div className="flex-1">
            <div className="flex items-center justify-between mb-1 gap-4">
              <span className="text-xs font-mono text-gray-300">
                {ev.function_name || ev.description}
              </span>
              <span className="text-[10px] text-gray-600 font-mono shrink-0">
                {ev.file_path}
                {ev.line_start ? `:${ev.line_start}` : ""}
              </span>
            </div>
            <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px] text-gray-500">
              <span className="rounded-full border border-amber-500/20 bg-amber-500/10 px-2 py-0.5 text-amber-300">
                fan-in {metrics.fanIn}
              </span>
              <span className="rounded-full border border-rose-500/20 bg-rose-500/10 px-2 py-0.5 text-rose-300">
                fan-out {metrics.fanOut}
              </span>
              <span>Higher values mean this symbol is more central to change risk.</span>
            </div>
            <div className="h-1 rounded-full bg-gray-800 overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width: `${Math.max(pct, 8)}%`,
                  background: `linear-gradient(90deg, #f97316, #ef4444)`,
                }}
              />
            </div>
          </div>
        </div>
      </button>
      {expandable && open && (
        <div className="px-4 pb-4 pl-10">
          <div className="rounded-lg border border-t-border/40 bg-gray-950/50 overflow-hidden">
            <div className="px-4 py-2 text-[11px] uppercase tracking-wider text-gray-500 border-b border-t-border/30">
              Hotspot Detail
            </div>
            <pre className="overflow-x-auto px-4 py-3 text-xs leading-6 text-gray-300 font-mono whitespace-pre-wrap">
              {ev.code_snippet}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */
export default function Dependencies() {
  const [tab, setTab] = useState<Tab>("cycles");
  const [results, setResults] = useState<Record<Tab, QueryResult | null>>({
    cycles: null,
    hotspots: null,
    coupling: null,
  });
  const [loading, setLoading] = useState<Record<Tab, boolean>>({
    cycles: false,
    hotspots: false,
    coupling: false,
  });

  const fetchTab = async (t: Tab) => {
    if (results[t]) return; // cached
    setLoading((prev) => ({ ...prev, [t]: true }));
    try {
      let r: QueryResult;
      if (t === "cycles") r = await api.cycles();
      else if (t === "hotspots") r = await api.hotspots();
      else r = await api.coupling();
      setResults((prev) => ({ ...prev, [t]: r }));
    } finally {
      setLoading((prev) => ({ ...prev, [t]: false }));
    }
  };

  useEffect(() => {
    fetchTab(tab);
  }, [tab]);

  const current = results[tab];
  const maxHotspot =
    current?.evidence?.reduce((max, ev) => {
      return Math.max(max, parseHotspotCount(ev.description));
    }, 0) ?? 1;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Dependencies</h1>
        <p className="text-sm text-gray-500 mt-1">
          Circular dependencies, hotspots, and coupling analysis
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        <TabBtn
          active={tab === "cycles"}
          label="Cycles"
          icon={RefreshCw}
          onClick={() => setTab("cycles")}
        />
        <TabBtn
          active={tab === "hotspots"}
          label="Hotspots"
          icon={Flame}
          onClick={() => setTab("hotspots")}
        />
        <TabBtn
          active={tab === "coupling"}
          label="Coupling"
          icon={Link2}
          onClick={() => setTab("coupling")}
        />
      </div>

      {/* Content */}
      {loading[tab] && (
        <div className="glass rounded-xl p-8 animate-pulse text-center text-gray-600 text-sm">
          Analyzing…
        </div>
      )}

      {current && (
        <>
          {/* Conclusion */}
          <div className="glass rounded-xl p-5">
            <p className="text-sm text-gray-300 leading-relaxed">
              {current.conclusion}
            </p>
          </div>

          {tab === "hotspots" && (
            <div className="glass rounded-xl p-5 border border-amber-500/15 bg-gradient-to-br from-amber-500/6 to-transparent">
              <div className="flex items-center gap-2 text-amber-300 mb-2">
                <Flame size={15} />
                <h2 className="text-sm font-semibold">What Hotspots Mean</h2>
              </div>
              <p className="text-sm text-gray-300 leading-relaxed">
                Hotspots are functions or methods with unusually high dependency traffic.
                <span className="text-gray-400"> Fan-in </span>
                counts how many other parts of the code depend on this symbol.
                <span className="text-gray-400"> Fan-out </span>
                counts how many other symbols it depends on.
              </p>
              <p className="text-xs text-gray-500 mt-3 leading-relaxed">
                In practice, higher fan-in usually means wider blast radius when a symbol changes,
                and higher fan-out usually means more implementation complexity. The bar below is
                scaled against the strongest hotspot in the current result set.
              </p>
            </div>
          )}

          {/* Tab-specific rendering */}
          {tab === "cycles" && (
            <div className="space-y-3">
              {current.evidence?.length ? (
                current.evidence.map((ev, i) => (
                  <CycleCard key={i} ev={ev} />
                ))
              ) : (
                <div className="glass rounded-xl p-8 text-center text-gray-600 text-sm">
                  No circular dependencies detected
                </div>
              )}
            </div>
          )}

          {tab === "hotspots" && (
            <div className="glass rounded-xl overflow-hidden divide-y divide-t-border/20">
              {current.evidence?.length ? (
                current.evidence.map((ev, i) => (
                  <HotspotRow key={i} ev={ev} maxCount={maxHotspot} />
                ))
              ) : (
                <div className="p-8 text-center text-gray-600 text-sm">
                  No hotspots above threshold
                </div>
              )}
            </div>
          )}

          {tab === "coupling" && (
            <ResultPanel result={current} />
          )}
        </>
      )}
    </div>
  );
}
