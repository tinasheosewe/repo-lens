import { useState } from "react";
import { Search, Zap } from "lucide-react";
import { api } from "../api/client";
import type { QueryResult } from "../types";
import ResultPanel from "../components/ResultPanel";
import GraphView from "../components/GraphView";

export default function Impact() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [highlightIds, setHighlightIds] = useState<Set<string>>(new Set());

  const run = async () => {
    const name = query.trim();
    if (!name) return;
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
      <div className="glass rounded-xl p-1">
        <div className="relative flex items-center">
          <Search size={18} className="absolute left-4 text-gray-500" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()}
            placeholder="Enter function, class, or file name…"
            className="w-full bg-transparent text-gray-200 placeholder:text-gray-600 pl-11 pr-24 py-3 text-sm focus:outline-none"
          />
          <button
            onClick={run}
            disabled={loading || !query.trim()}
            className="absolute right-1 flex items-center gap-1.5 bg-t-primary hover:bg-t-primary/80 disabled:opacity-40 text-white text-xs font-medium px-4 py-1.5 rounded-lg transition-colors"
          >
            <Zap size={13} />
            Analyze
          </button>
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
