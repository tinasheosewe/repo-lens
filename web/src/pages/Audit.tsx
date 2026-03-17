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

      <ResultPanel result={results[tab]} loading={loading[tab]} />
    </div>
  );
}