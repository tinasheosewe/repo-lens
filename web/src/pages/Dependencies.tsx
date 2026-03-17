import { useEffect, useState } from "react";
import { RefreshCw, Flame, Link2 } from "lucide-react";
import { api } from "../api/client";
import type { QueryResult } from "../types";
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
function CycleCard({ ev }: { ev: { description: string; location?: string } }) {
  const parts = ev.description.split(" → ");
  return (
    <div className="glass rounded-xl p-4 hover:border-t-primary/20 transition-colors">
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
  );
}

/* ------------------------------------------------------------------ */
/* Hotspot bar                                                         */
/* ------------------------------------------------------------------ */
function HotspotRow({
  ev,
  maxCount,
}: {
  ev: { description: string; location?: string };
  maxCount: number;
}) {
  // Try to parse count from description e.g. "module (fan-in: 5)"
  const match = ev.description.match(/\((\d+)\s/);
  const count = match ? parseInt(match[1]) : 1;
  const pct = maxCount > 0 ? (count / maxCount) * 100 : 20;

  return (
    <div className="py-2.5 px-4 hover:bg-white/[0.02] transition-colors">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-mono text-gray-300">
          {ev.description}
        </span>
        {ev.location && (
          <span className="text-[10px] text-gray-600 font-mono">
            {ev.location}
          </span>
        )}
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
      const m = ev.description.match(/\((\d+)\s/);
      return m ? Math.max(max, parseInt(m[1])) : max;
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
