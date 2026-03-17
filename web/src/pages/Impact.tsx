import { useState } from "react";
import { Zap } from "lucide-react";
import { api } from "../api/client";
import type { Evidence, QueryResult } from "../types";
import ResultPanel from "../components/ResultPanel";
import GraphView from "../components/GraphView";
import SymbolPicker, { getEvidenceLabel } from "../components/SymbolPicker";

export default function Impact() {
  const [query, setQuery] = useState("");
  const [selectedQuery, setSelectedQuery] = useState<Evidence | null>(null);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [highlightIds, setHighlightIds] = useState<Set<string>>(new Set());

  const matchesSelectedValue = (selected: Evidence | null, value: string) => {
    return !!selected && getEvidenceLabel(selected) === value;
  };

  const run = async () => {
    if (!selectedQuery) return;

    const name = getEvidenceLabel(selectedQuery);
    setLoading(true);
    try {
      const r = await api.impact(name);
      setResult(r);
      // Use affected_nodes from the result
      setHighlightIds(new Set(r.affected_nodes ?? []));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Impact Analysis</h1>
        <p className="text-sm text-gray-500 mt-1">
          See what breaks when you change a component
        </p>
      </div>

      {/* Search */}
      <div className="glass rounded-xl p-4">
        <div className="mb-4 rounded-xl border border-t-primary/15 bg-t-primary/5 px-4 py-3 text-sm text-gray-300">
          Search for a symbol live, select the exact target, then run impact analysis on that selected node.
        </div>

        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-start">
          <SymbolPicker
            label="Target"
            value={query}
            selected={selectedQuery}
            placeholder="Search function, class, or file name..."
            onValueChange={(value) => {
              setQuery(value);
              if (!matchesSelectedValue(selectedQuery, value)) {
                setSelectedQuery(null);
              }
              setResult(null);
              setHighlightIds(new Set());
            }}
            onSelect={(ev) => {
              const label = getEvidenceLabel(ev);
              setQuery(label);
              setSelectedQuery(ev);
              setResult(null);
              setHighlightIds(new Set());
            }}
          />

          <div className="md:pt-8">
            <button
              onClick={run}
              disabled={loading || !selectedQuery}
              className="w-full flex items-center justify-center gap-1.5 bg-t-primary hover:bg-t-primary/80 disabled:opacity-40 text-white text-xs font-medium px-4 py-2.5 rounded-lg transition-colors md:w-auto"
            >
              <Zap size={13} />
              Analyze
            </button>
          </div>
        </div>
      </div>

      {/* Results */}
      <div className="grid lg:grid-cols-2 gap-4">
        <ResultPanel result={result} loading={loading} />

        {result && (
          <div className="glass rounded-xl overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-3 border-b border-t-border/50">
              <Zap size={14} className="text-rose-400" />
              <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
                Impact Graph
              </span>
            </div>
            <GraphView
              className="h-[400px]"
              highlightIds={highlightIds}
            />
          </div>
        )}
      </div>
    </div>
  );
}
