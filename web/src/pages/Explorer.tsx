import { useRef, useState } from "react";
import { Route, ArrowRight } from "lucide-react";
import { api } from "../api/client";
import type { Evidence, QueryResult } from "../types";
import ResultPanel from "../components/ResultPanel";
import PathResultPanel from "../components/PathResultPanel";
import SymbolPicker, { getEvidenceLabel } from "../components/SymbolPicker";

export default function Explorer() {
  /* ----- path-finding state ----- */
  const [pathFrom, setPathFrom] = useState("");
  const [pathTo, setPathTo] = useState("");
  const [selectedFrom, setSelectedFrom] = useState<Evidence | null>(null);
  const [selectedTo, setSelectedTo] = useState<Evidence | null>(null);
  const [pathResult, setPathResult] = useState<QueryResult | null>(null);
  const [pathLoading, setPathLoading] = useState(false);
  const toInputRef = useRef<HTMLInputElement>(null);

  const matchesSelectedValue = (selected: Evidence | null, value: string) => {
    return !!selected && getEvidenceLabel(selected) === value;
  };

  const runPath = async () => {
    if (!selectedFrom || !selectedTo) return;

    const f = getEvidenceLabel(selectedFrom);
    const t = getEvidenceLabel(selectedTo);
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
          Choose a source and target symbol, then inspect the connection path between them
        </p>
      </div>

      {/* -------- Path finding section -------- */}
      <section className="space-y-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-300">
          <Route size={15} className="text-cyan-400" />
          Path Finder
        </h2>

        <div className="glass rounded-xl p-4">
          <div className="mb-4 rounded-xl border border-cyan-500/15 bg-cyan-500/5 px-4 py-3 text-sm text-gray-300">
            Type in either field to search symbols live. Use arrow keys to move through matches and press Enter to select a symbol for that side of the path.
          </div>

          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)_auto] md:items-start">
            <SymbolPicker
              label="From"
              value={pathFrom}
              selected={selectedFrom}
              placeholder="Search source symbol..."
              onValueChange={(value) => {
                setPathFrom(value);
                if (!matchesSelectedValue(selectedFrom, value)) {
                  setSelectedFrom(null);
                }
                setPathResult(null);
              }}
              onSelect={(ev) => {
                const label = getEvidenceLabel(ev);
                setPathFrom(label);
                setSelectedFrom(ev);
                setPathResult(null);
                window.setTimeout(() => toInputRef.current?.focus(), 0);
              }}
            />

            <div className="hidden md:flex h-full items-center justify-center pt-8">
              <ArrowRight size={18} className="text-gray-600 shrink-0" />
            </div>

            <SymbolPicker
              label="To"
              value={pathTo}
              selected={selectedTo}
              inputRef={toInputRef}
              placeholder="Search target symbol..."
              onValueChange={(value) => {
                setPathTo(value);
                if (!matchesSelectedValue(selectedTo, value)) {
                  setSelectedTo(null);
                }
                setPathResult(null);
              }}
              onSelect={(ev) => {
                const label = getEvidenceLabel(ev);
                setPathTo(label);
                setSelectedTo(ev);
                setPathResult(null);
              }}
            />

            <div className="md:pt-8">
              <button
                onClick={runPath}
                disabled={pathLoading || !selectedFrom || !selectedTo}
                className="w-full bg-cyan-500 hover:bg-cyan-500/80 disabled:opacity-40 text-white text-xs font-medium px-4 py-2.5 rounded-lg transition-colors shrink-0 md:w-auto"
              >
                Find Path
              </button>
            </div>
          </div>
        </div>

        {pathLoading ? (
          <ResultPanel result={null} loading />
        ) : pathResult ? (
          <PathResultPanel result={pathResult} />
        ) : null}
      </section>
    </div>
  );
}
