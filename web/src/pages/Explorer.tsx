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

interface PathNodeDetail {
  id: string;
  name: string;
  node_type: string;
  file_path: string;
  line_start: number | null;
  line_end: number | null;
  code_snippet: string | null;
  step: number;
  step_count: number;
}

function isPathNodeDetail(value: unknown): value is PathNodeDetail {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.id === "string" &&
    typeof candidate.name === "string" &&
    typeof candidate.file_path === "string" &&
    typeof candidate.step === "number" &&
    typeof candidate.step_count === "number"
  );
}

function getPathDetails(result: QueryResult | null): PathNodeDetail[][] {
  const raw = result?.metadata?.path_details;
  if (!Array.isArray(raw)) return [];

  return raw
    .map((path) =>
      Array.isArray(path) ? path.filter(isPathNodeDetail) : [],
    )
    .filter((path) => path.length > 0);
}

function PathNodeCard({
  node,
  selected,
  onSelect,
}: {
  node: PathNodeDetail;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-[320px] shrink-0 rounded-xl border overflow-hidden text-left transition-colors md:w-[360px] ${
        selected
          ? "border-cyan-400/40 bg-cyan-500/10"
          : "border-t-border/40 bg-gray-950/35 hover:border-cyan-500/25 hover:bg-gray-950/55"
      }`}
    >
      <div className="px-4 py-3">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-cyan-500/15 text-[11px] font-semibold text-cyan-300">
            {node.step}
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-xs uppercase tracking-wider text-gray-500">{node.node_type}</div>
            <div className="text-sm font-medium text-gray-200 break-words">{node.name}</div>
            <div className="mt-1 text-[11px] font-mono text-gray-500 break-all">
              {node.file_path}
              {node.line_start ? `:${node.line_start}` : ""}
            </div>
          </div>
        </div>
      </div>
      <div className="border-t border-t-border/30 px-4 py-2 text-[11px] text-gray-500">
        {node.code_snippet ? "Click to inspect source below" : "No source snippet available"}
      </div>
    </button>
  );
}

function PathResultPanel({ result }: { result: QueryResult }) {
  const pathDetails = getPathDetails(result);
  const [selectedNodes, setSelectedNodes] = useState<Record<number, string>>({});

  if (!pathDetails.length) {
    return <ResultPanel result={result} />;
  }

  return (
    <div className="glass rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-t-border/50">
        <h3 className="text-sm font-semibold text-gray-200">Resolved Paths</h3>
        <p className="mt-1 text-sm text-gray-400 leading-relaxed">{result.conclusion}</p>
        <p className="mt-3 text-xs text-gray-500">
          Read each lane from left to right. Each card is one symbol in the call chain, and the arrows show the order of execution through the path.
        </p>
      </div>

      <div className="px-5 py-5 space-y-4">
        {pathDetails.map((path, pathIndex) => (
          <div key={path[0]?.id ?? pathIndex} className="rounded-xl border border-cyan-500/10 bg-cyan-500/5 p-4">
            {(() => {
              const selectedNode = path.find((node) => node.id === selectedNodes[pathIndex]) ?? path[0];

              return (
                <>
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-wider text-cyan-300">Path {pathIndex + 1}</div>
                <div className="text-sm text-gray-400">
                  {path.length} step{path.length === 1 ? "" : "s"}
                </div>
              </div>
              <div className="text-xs text-gray-500">
                {path.map((node) => node.name).join(" -> ")}
              </div>
            </div>

            <div className="overflow-x-auto pb-3">
              <div className="flex min-w-max items-stretch gap-3">
                {path.map((node, index) => (
                  <div key={node.id} className="flex items-center gap-3">
                    <PathNodeCard
                      node={node}
                      selected={selectedNode.id === node.id}
                      onSelect={() =>
                        setSelectedNodes((current) => ({
                          ...current,
                          [pathIndex]: node.id,
                        }))
                      }
                    />
                  {index < path.length - 1 && (
                      <div className="flex shrink-0 items-center justify-center text-cyan-300/70 px-1">
                        <ArrowRight size={18} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-t-border/40 bg-gray-950/45 overflow-hidden">
              <div className="px-4 py-3 border-b border-t-border/30">
                <div className="text-[11px] uppercase tracking-wider text-gray-500">Selected Step</div>
                <div className="mt-1 flex items-center gap-2 text-sm text-gray-200">
                  <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-cyan-500/15 text-[11px] font-semibold text-cyan-300">
                    {selectedNode.step}
                  </span>
                  <span>{selectedNode.name}</span>
                </div>
                <div className="mt-1 text-[11px] font-mono text-gray-500 break-all">
                  {selectedNode.file_path}
                  {selectedNode.line_start ? `:${selectedNode.line_start}` : ""}
                </div>
              </div>

              {selectedNode.code_snippet ? (
                <pre className="overflow-x-auto px-4 py-4 whitespace-pre-wrap text-xs leading-6 text-gray-300 font-mono">
                  {selectedNode.code_snippet}
                </pre>
              ) : (
                <div className="px-4 py-4 text-sm text-gray-500">
                  No source snippet is available for this node.
                </div>
              )}
            </div>
                </>
              );
            })()}
          </div>
        ))}
      </div>
    </div>
  );
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

        {pathLoading ? (
          <ResultPanel result={null} loading />
        ) : pathResult ? (
          <PathResultPanel result={pathResult} />
        ) : null}
      </section>
    </div>
  );
}
