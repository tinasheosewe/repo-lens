import { useEffect, useRef, useState } from "react";
import { Route, Workflow as WorkflowIcon } from "lucide-react";
import { api } from "../api/client";
import type { Evidence, QueryResult } from "../types";
import PathResultPanel from "../components/PathResultPanel";
import ResultPanel from "../components/ResultPanel";
import SymbolPicker, { getEvidenceLabel } from "../components/SymbolPicker";

type Tab = "entries" | "call-flow";

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

export default function Flows() {
  const [tab, setTab] = useState<Tab>("entries");
  const [entryKind, setEntryKind] = useState("all");
  const [entryResult, setEntryResult] = useState<QueryResult | null>(null);
  const [entryLoading, setEntryLoading] = useState(false);
  const [callResult, setCallResult] = useState<QueryResult | null>(null);
  const [callLoading, setCallLoading] = useState(false);
  const [callValue, setCallValue] = useState("");
  const [selectedCall, setSelectedCall] = useState<Evidence | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (tab !== "entries") return;
    setEntryLoading(true);
    api.entryFlows(entryKind).then(setEntryResult).finally(() => setEntryLoading(false));
  }, [entryKind, tab]);

  const runCallFlow = async () => {
    if (!selectedCall) return;
    setCallLoading(true);
    try {
      setCallResult(await api.callFlow(getEvidenceLabel(selectedCall)));
    } finally {
      setCallLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-white">Flows</h1>
        <p className="text-sm text-gray-500 mt-1">Trace route, CLI, and job entry paths, then explore downstream call flows from any symbol.</p>
      </div>

      <div className="flex gap-2">
        <TabButton active={tab === "entries"} label="Entry Flows" icon={Route} onClick={() => setTab("entries")} />
        <TabButton active={tab === "call-flow"} label="Call Flow" icon={WorkflowIcon} onClick={() => setTab("call-flow")} />
      </div>

      {tab === "entries" && (
        <>
          <div className="glass rounded-xl p-4 flex flex-wrap items-center gap-3">
            <label className="text-xs uppercase tracking-wider text-gray-500">Entry Kind</label>
            <select
              value={entryKind}
              onChange={(event) => setEntryKind(event.target.value)}
              className="bg-gray-800/50 text-gray-200 px-4 py-2.5 text-sm rounded-lg border border-t-border focus:border-t-primary/50 focus:outline-none transition-colors"
            >
              <option value="all">All</option>
              <option value="route">Routes</option>
              <option value="job">Jobs</option>
              <option value="cli">CLI</option>
            </select>
          </div>
          {entryResult ? <PathResultPanel result={entryResult} title="Entry Flows" helperText="These lanes start at detected route, CLI, or job entry points and trace downstream call paths." /> : <ResultPanel result={null} loading={entryLoading} />}
        </>
      )}

      {tab === "call-flow" && (
        <>
          <div className="glass rounded-xl p-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-start">
            <SymbolPicker
              label="Start Symbol"
              value={callValue}
              selected={selectedCall}
              inputRef={inputRef}
              placeholder="Search function, class, or file name..."
              onValueChange={(value) => {
                setCallValue(value);
                if (!selectedCall || getEvidenceLabel(selectedCall) !== value) {
                  setSelectedCall(null);
                }
                setCallResult(null);
              }}
              onSelect={(evidence) => {
                const label = getEvidenceLabel(evidence);
                setCallValue(label);
                setSelectedCall(evidence);
                setCallResult(null);
              }}
            />
            <div className="md:pt-8">
              <button
                type="button"
                onClick={runCallFlow}
                disabled={callLoading || !selectedCall}
                className="rounded-lg bg-t-primary px-4 py-2.5 text-sm font-medium text-white hover:bg-t-primary/80 disabled:opacity-40 transition-colors"
              >
                {callLoading ? "Tracing..." : "Trace Flow"}
              </button>
            </div>
          </div>
          {callResult ? <PathResultPanel result={callResult} title="Call Flow" helperText="Each lane shows one downstream execution path from the selected starting symbol." /> : <ResultPanel result={null} loading={callLoading} />}
        </>
      )}
    </div>
  );
}