import { useEffect, useRef, useState, type KeyboardEvent, type RefObject } from "react";
import { Search, Route, ArrowRight, CornerDownLeft } from "lucide-react";
import { api } from "../api/client";
import type { Evidence, QueryResult } from "../types";
import ResultPanel from "../components/ResultPanel";

function getEvidenceLabel(ev: Evidence): string {
  if (ev.function_name) return ev.function_name;

  const [, ...rest] = ev.description.split(": ");
  return rest.join(": ") || ev.file_path;
}

interface SymbolPickerProps {
  label: string;
  value: string;
  selected: Evidence | null;
  placeholder: string;
  inputRef?: RefObject<HTMLInputElement>;
  onValueChange: (value: string) => void;
  onSelect: (ev: Evidence) => void;
}

function SymbolPicker({
  label,
  value,
  selected,
  placeholder,
  inputRef,
  onValueChange,
  onSelect,
}: SymbolPickerProps) {
  const [results, setResults] = useState<Evidence[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [open, setOpen] = useState(false);
  const requestId = useRef(0);

  useEffect(() => {
    const q = value.trim();
    const selectedLabel = selected ? getEvidenceLabel(selected) : null;

    if (!q) {
      setResults([]);
      setLoading(false);
      setActiveIndex(0);
      setOpen(false);
      return;
    }

    if (selectedLabel === q) {
      setLoading(false);
      setOpen(false);
      return;
    }

    const currentRequest = ++requestId.current;
    const timeout = window.setTimeout(async () => {
      setLoading(true);
      try {
        const result = await api.search(q);
        if (requestId.current !== currentRequest) return;
        setResults(result.evidence.slice(0, 8));
        setActiveIndex(0);
        setOpen(true);
      } finally {
        if (requestId.current === currentRequest) {
          setLoading(false);
        }
      }
    }, 180);

    return () => window.clearTimeout(timeout);
  }, [selected, value]);

  const selectEvidence = (ev: Evidence) => {
    onSelect(ev);
    setResults([]);
    setOpen(false);
    setActiveIndex(0);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (!open || !results.length) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((index) => (index + 1) % results.length);
      return;
    }

    if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((index) => (index === 0 ? results.length - 1 : index - 1));
      return;
    }

    if (e.key === "Enter") {
      e.preventDefault();
      selectEvidence(results[activeIndex]);
      return;
    }

    if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
    }
  };

  return (
    <div className="relative flex-1">
      <div className="mb-2 flex items-center justify-between">
        <label className="text-xs font-medium uppercase tracking-wider text-gray-500">
          {label}
        </label>
        <div className="flex items-center gap-2 text-[11px] text-gray-500">
          <span>{loading ? "Searching..." : selected ? "Selected" : "Type to search"}</span>
          <span className="inline-flex items-center gap-1 rounded-full border border-t-border/60 px-2 py-1 text-gray-400">
            <CornerDownLeft size={11} />
            Select
          </span>
        </div>
      </div>

      <div className="relative">
        <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500" />
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => {
            onValueChange(e.target.value);
            setOpen(true);
          }}
          onFocus={() => {
            if (results.length || loading) {
              setOpen(true);
            }
          }}
          onBlur={() => {
            window.setTimeout(() => setOpen(false), 120);
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="w-full bg-gray-800/50 text-gray-200 placeholder:text-gray-600 pl-10 pr-4 py-2.5 text-sm rounded-lg border border-t-border focus:border-t-primary/50 focus:outline-none transition-colors"
        />
      </div>

      {selected && value.trim() === getEvidenceLabel(selected) && (
        <div className="mt-2 rounded-lg border border-emerald-500/20 bg-emerald-500/8 px-3 py-2 text-[11px] text-emerald-200">
          {selected.file_path}
          {selected.line_start ? `:${selected.line_start}` : ""}
        </div>
      )}

      {open && value.trim() && (
        <div className="absolute z-20 mt-2 w-full overflow-hidden rounded-xl border border-t-border/60 bg-t-panel shadow-2xl shadow-black/30">
          {results.length > 0 ? (
            <div className="max-h-80 overflow-y-auto p-2">
              {results.map((ev, index) => {
                const active = index === activeIndex;
                const isSelected = selected === ev;

                return (
                  <button
                    key={`${ev.file_path}:${ev.function_name ?? ev.description}:${ev.line_start ?? 0}`}
                    type="button"
                    onMouseEnter={() => setActiveIndex(index)}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => selectEvidence(ev)}
                    className={`w-full rounded-lg px-3 py-2 text-left transition-colors ${
                      isSelected
                        ? "bg-t-primary/15 border border-t-primary/30"
                        : active
                          ? "bg-white/[0.06]"
                          : "hover:bg-white/[0.04]"
                    }`}
                  >
                    <div className="text-sm text-gray-200">{getEvidenceLabel(ev)}</div>
                    <div className="mt-0.5 text-[11px] text-gray-500 font-mono">
                      {ev.file_path}
                      {ev.line_start ? `:${ev.line_start}` : ""}
                    </div>
                  </button>
                );
              })}
            </div>
          ) : !loading ? (
            <div className="px-4 py-3 text-sm text-gray-500">No matches found.</div>
          ) : null}
        </div>
      )}
    </div>
  );
}

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

        <ResultPanel result={pathResult} loading={pathLoading} />
      </section>
    </div>
  );
}
