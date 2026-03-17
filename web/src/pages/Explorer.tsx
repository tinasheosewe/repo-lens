import { useState } from "react";
import { Search, Route, ArrowRight } from "lucide-react";
import { api } from "../api/client";
import type { QueryResult } from "../types";
import ResultPanel from "../components/ResultPanel";

export default function Explorer() {
  /* ----- search state ----- */
  const [searchQ, setSearchQ] = useState("");
  const [searchResult, setSearchResult] = useState<QueryResult | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);

  /* ----- path-finding state ----- */
  const [pathFrom, setPathFrom] = useState("");
  const [pathTo, setPathTo] = useState("");
  const [pathResult, setPathResult] = useState<QueryResult | null>(null);
  const [pathLoading, setPathLoading] = useState(false);

  const runSearch = async () => {
    const q = searchQ.trim();
    if (!q) return;
    setSearchLoading(true);
    try {
      setSearchResult(await api.search(q));
    } finally {
      setSearchLoading(false);
    }
  };

  const runPath = async () => {
    const f = pathFrom.trim();
    const t = pathTo.trim();
    if (!f || !t) return;
    setPathLoading(true);
    try {
      setPathResult(await api.path(f, t));
    } finally {
      setPathLoading(false);
    }
  };

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Explorer</h1>
        <p className="text-sm text-gray-500 mt-1">
          Search components and find connection paths
        </p>
      </div>

      {/* -------- Search section -------- */}
      <section className="space-y-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-300">
          <Search size={15} className="text-t-primary" />
          Search
        </h2>

        <div className="glass rounded-xl p-1">
          <div className="relative flex items-center">
            <Search size={16} className="absolute left-4 text-gray-500" />
            <input
              type="text"
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runSearch()}
              placeholder="Search by name (e.g. authenticate, UserModel)…"
              className="w-full bg-transparent text-gray-200 placeholder:text-gray-600 pl-10 pr-20 py-3 text-sm focus:outline-none"
            />
            <button
              onClick={runSearch}
              disabled={searchLoading || !searchQ.trim()}
              className="absolute right-1 bg-t-primary hover:bg-t-primary/80 disabled:opacity-40 text-white text-xs font-medium px-4 py-1.5 rounded-lg transition-colors"
            >
              Search
            </button>
          </div>
        </div>

        <ResultPanel result={searchResult} loading={searchLoading} />
      </section>

      {/* -------- Path finding section -------- */}
      <section className="space-y-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-300">
          <Route size={15} className="text-cyan-400" />
          Path Finder
        </h2>

        <div className="glass rounded-xl p-4">
          <div className="flex items-center gap-3">
            <input
              type="text"
              value={pathFrom}
              onChange={(e) => setPathFrom(e.target.value)}
              placeholder="From component…"
              className="flex-1 bg-gray-800/50 text-gray-200 placeholder:text-gray-600 px-4 py-2.5 text-sm rounded-lg border border-t-border focus:border-t-primary/50 focus:outline-none transition-colors"
            />
            <ArrowRight size={18} className="text-gray-600 shrink-0" />
            <input
              type="text"
              value={pathTo}
              onChange={(e) => setPathTo(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runPath()}
              placeholder="To component…"
              className="flex-1 bg-gray-800/50 text-gray-200 placeholder:text-gray-600 px-4 py-2.5 text-sm rounded-lg border border-t-border focus:border-t-primary/50 focus:outline-none transition-colors"
            />
            <button
              onClick={runPath}
              disabled={
                pathLoading || !pathFrom.trim() || !pathTo.trim()
              }
              className="bg-cyan-500 hover:bg-cyan-500/80 disabled:opacity-40 text-white text-xs font-medium px-4 py-2 rounded-lg transition-colors shrink-0"
            >
              Find Path
            </button>
          </div>
        </div>

        <ResultPanel result={pathResult} loading={pathLoading} />
      </section>
    </div>
  );
}
