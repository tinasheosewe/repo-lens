import { useEffect, useState } from "react";
import { ArchiveX, ActivitySquare } from "lucide-react";
import { api } from "../api/client";
import type { QueryResult } from "../types";
import ResultPanel from "../components/ResultPanel";

type Tab = "stale" | "criticality";

function TabButton({ active, label, onClick, icon: Icon }: { active: boolean; label: string; onClick: () => void; icon: React.ElementType }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-1.5 px-4 py-2 text-xs font-medium rounded-lg transition-all duration-200 ${
        active ? "bg-t-primary/15 text-t-primary border border-t-primary/30" : "text-gray-500 hover:text-gray-300 border border-transparent"
      }`}
    >
      <Icon size={14} />
      {label}
    </button>
  );
}

type CriticalityDetail = {
  node_id: string;
  name: string;
  file_path: string;
  score: number;
  fan_in: number;
  fan_out: number;
  transitive_dependents: number;
};

function CriticalityCard({
  label,
  item,
  metric,
}: {
  label: string;
  item: CriticalityDetail | null;
  metric: "fan_in" | "fan_out";
}) {
  return (
    <div className="glass rounded-xl p-5">
      <div className="text-xs uppercase tracking-wider text-gray-500 mb-2">{label}</div>
      {item ? (
        <>
          <div className="text-lg font-semibold text-white">{item.name}</div>
          <div className="mt-1 text-xs font-mono text-gray-500 break-all">{item.file_path}</div>
          <div className="mt-4 flex items-end justify-between gap-3">
            <div>
              <div className="text-[11px] uppercase tracking-wider text-gray-500">
                {metric === "fan_in" ? "Fan In" : "Fan Out"}
              </div>
              <div className="text-3xl font-bold text-white">{item[metric]}</div>
            </div>
            <div className="text-right text-xs text-gray-500">
              <div>Criticality {item.score.toFixed(3)}</div>
              <div>{item.transitive_dependents} downstream dependents</div>
            </div>
          </div>
        </>
      ) : (
        <div className="text-sm text-gray-500">No criticality details available yet.</div>
      )}
    </div>
  );
}

export default function Audit() {
  const [tab, setTab] = useState<Tab>("stale");
  const [results, setResults] = useState<Record<Tab, QueryResult | null>>({ stale: null, criticality: null });
  const [loading, setLoading] = useState<Record<Tab, boolean>>({ stale: false, criticality: false });

  useEffect(() => {
    if (results[tab]) return;
    setLoading((current) => ({ ...current, [tab]: true }));
    const promise = tab === "stale" ? api.staleModules() : api.criticality();
    promise.then((result) => setResults((current) => ({ ...current, [tab]: result }))).finally(() => {
      setLoading((current) => ({ ...current, [tab]: false }));
    });
  }, [results, tab]);

  const criticalityRankings = Array.isArray(results.criticality?.metadata?.rankings)
    ? (results.criticality?.metadata?.rankings as CriticalityDetail[])
    : [];
  const topFanIn = criticalityRankings.reduce<CriticalityDetail | null>(
    (best, item) => (best === null || item.fan_in > best.fan_in ? item : best),
    null,
  );
  const topFanOut = criticalityRankings.reduce<CriticalityDetail | null>(
    (best, item) => (best === null || item.fan_out > best.fan_out ? item : best),
    null,
  );

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-white">Audit</h1>
        <p className="text-sm text-gray-500 mt-1">Stale module detection and graph-based criticality ranking.</p>
      </div>

      <div className="flex gap-2">
        <TabButton active={tab === "stale"} label="Stale Modules" icon={ArchiveX} onClick={() => setTab("stale")} />
        <TabButton active={tab === "criticality"} label="Criticality" icon={ActivitySquare} onClick={() => setTab("criticality")} />
      </div>

      <div className="glass rounded-xl p-4 border border-t-border/40">
        <div className="text-xs uppercase tracking-wider text-gray-500 mb-2">
          {tab === "stale" ? "Stale Modules" : "Criticality"}
        </div>
        <p className="text-sm text-gray-300 leading-relaxed">
          {tab === "stale"
            ? "Flags modules with low observed graph activity so you can review code that may be obsolete, unreferenced, or overdue for cleanup."
            : "Ranks symbols by centrality, dependency spread, fan-in, and fan-out to highlight code that is structurally risky to change."}
        </p>
      </div>

      {tab === "criticality" && (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <CriticalityCard label="Highest Fan In" item={topFanIn} metric="fan_in" />
            <CriticalityCard label="Highest Fan Out" item={topFanOut} metric="fan_out" />
          </div>

          <div className="glass rounded-xl p-4 border border-t-border/40">
            <div className="text-xs uppercase tracking-wider text-gray-500 mb-3">How To Read These</div>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-xl border border-cyan-500/15 bg-cyan-500/5 p-4">
                <div className="text-sm font-medium text-cyan-200 mb-1">Fan In</div>
                <p className="text-sm text-gray-300 leading-relaxed">
                  Fan in is how many other nodes point into this symbol. High fan in usually means many parts of the repo rely on it, so changing it can have broad impact.
                </p>
              </div>
              <div className="rounded-xl border border-amber-500/15 bg-amber-500/5 p-4">
                <div className="text-sm font-medium text-amber-200 mb-1">Fan Out</div>
                <p className="text-sm text-gray-300 leading-relaxed">
                  Fan out is how many other nodes this symbol reaches outward to. High fan out usually means the symbol coordinates many dependencies and can be harder to reason about or isolate.
                </p>
              </div>
            </div>
          </div>
        </>
      )}

      <ResultPanel result={results[tab]} loading={loading[tab]} />
    </div>
  );
}