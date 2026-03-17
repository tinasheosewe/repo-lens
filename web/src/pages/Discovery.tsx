import { useEffect, useState } from "react";
import { BookMarked, MessageSquareText, Search, History } from "lucide-react";
import { api } from "../api/client";
import type { QueryResult } from "../types";
import ResultPanel from "../components/ResultPanel";

type Tab = "onboarding" | "ask" | "concept" | "drift";

const TAB_DESCRIPTIONS: Record<Tab, { title: string; description: string }> = {
  onboarding: {
    title: "Onboarding",
    description: "Build a quick mental model of the repository by surfacing core subsystems, entry flows, and high-signal starting points.",
  },
  ask: {
    title: "Ask Repo",
    description: "Send natural-language architecture questions through the repo context to get grounded answers instead of raw keyword search.",
  },
  concept: {
    title: "Concept Search",
    description: "Search by domain idea rather than exact symbol name to find related validators, services, handlers, and modules.",
  },
  drift: {
    title: "Repo Drift",
    description: "Shows historical change drift by highlighting files that frequently move together or carry concentrated churn, which helps spot unstable boundaries and likely change-coupling.",
  },
};

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

export default function Discovery() {
  const [tab, setTab] = useState<Tab>("onboarding");
  const [results, setResults] = useState<Record<Tab, QueryResult | null>>({
    onboarding: null,
    ask: null,
    concept: null,
    drift: null,
  });
  const [loading, setLoading] = useState<Record<Tab, boolean>>({
    onboarding: false,
    ask: false,
    concept: false,
    drift: false,
  });
  const [question, setQuestion] = useState("");
  const [concept, setConcept] = useState("");

  useEffect(() => {
    if (tab === "onboarding" && !results.onboarding) {
      setLoading((current) => ({ ...current, onboarding: true }));
      api.onboarding().then((result) => setResults((current) => ({ ...current, onboarding: result }))).finally(() => {
        setLoading((current) => ({ ...current, onboarding: false }));
      });
    }
    if (tab === "drift" && !results.drift) {
      setLoading((current) => ({ ...current, drift: true }));
      api.historyDrift().then((result) => setResults((current) => ({ ...current, drift: result }))).finally(() => {
        setLoading((current) => ({ ...current, drift: false }));
      });
    }
  }, [results.drift, results.onboarding, tab]);

  const ask = async () => {
    if (!question.trim()) return;
    setLoading((current) => ({ ...current, ask: true }));
    try {
      const result = await api.askArchitecture(question.trim());
      setResults((current) => ({ ...current, ask: result }));
    } finally {
      setLoading((current) => ({ ...current, ask: false }));
    }
  };

  const runConceptSearch = async () => {
    if (!concept.trim()) return;
    setLoading((current) => ({ ...current, concept: true }));
    try {
      const result = await api.conceptSearch(concept.trim());
      setResults((current) => ({ ...current, concept: result }));
    } finally {
      setLoading((current) => ({ ...current, concept: false }));
    }
  };

  const current = results[tab];
  const subsystems = Array.isArray(results.onboarding?.metadata?.subsystems)
    ? (results.onboarding?.metadata?.subsystems as Array<[string, number]>)
    : [];
  const cochangePairs = Array.isArray(results.drift?.metadata?.cochange_pairs)
    ? (results.drift?.metadata?.cochange_pairs as Array<{ pair: string[]; count: number }>)
    : [];

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-white">Discovery</h1>
        <p className="text-sm text-gray-500 mt-1">Onboarding, natural-language repo questions, concept search, and historical drift.</p>
      </div>

      <div className="flex flex-wrap gap-2">
        <TabButton active={tab === "onboarding"} label="Onboarding" icon={BookMarked} onClick={() => setTab("onboarding")} />
        <TabButton active={tab === "ask"} label="Ask Repo" icon={MessageSquareText} onClick={() => setTab("ask")} />
        <TabButton active={tab === "concept"} label="Concept Search" icon={Search} onClick={() => setTab("concept")} />
        <TabButton active={tab === "drift"} label="History Drift" icon={History} onClick={() => setTab("drift")} />
      </div>

      <div className="glass rounded-xl p-4 border border-t-border/40">
        <div className="text-xs uppercase tracking-wider text-gray-500 mb-2">{TAB_DESCRIPTIONS[tab].title}</div>
        <p className="text-sm text-gray-300 leading-relaxed">{TAB_DESCRIPTIONS[tab].description}</p>
      </div>

      {tab === "ask" && (
        <div className="glass rounded-xl p-4 space-y-3">
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask a repository architecture question..."
            className="w-full min-h-[120px] bg-gray-800/50 text-gray-200 placeholder:text-gray-600 px-4 py-3 text-sm rounded-lg border border-t-border focus:border-t-primary/50 focus:outline-none transition-colors"
          />
          <button
            type="button"
            onClick={ask}
            disabled={loading.ask || !question.trim()}
            className="rounded-lg bg-t-primary px-4 py-2.5 text-sm font-medium text-white hover:bg-t-primary/80 disabled:opacity-40 transition-colors"
          >
            {loading.ask ? "Thinking..." : "Ask with LLM"}
          </button>
        </div>
      )}

      {tab === "concept" && (
        <div className="glass rounded-xl p-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
          <input
            type="text"
            value={concept}
            onChange={(event) => setConcept(event.target.value)}
            placeholder="validators, controllers, services, repositories..."
            className="w-full bg-gray-800/50 text-gray-200 placeholder:text-gray-600 px-4 py-3 text-sm rounded-lg border border-t-border focus:border-t-primary/50 focus:outline-none transition-colors"
          />
          <button
            type="button"
            onClick={runConceptSearch}
            disabled={loading.concept || !concept.trim()}
            className="rounded-lg bg-t-primary px-4 py-2.5 text-sm font-medium text-white hover:bg-t-primary/80 disabled:opacity-40 transition-colors"
          >
            {loading.concept ? "Searching..." : "Search"}
          </button>
        </div>
      )}

      {(tab === "onboarding" && subsystems.length > 0) && (
        <div className="glass rounded-xl p-5">
          <div className="text-xs uppercase tracking-wider text-gray-500 mb-3">Subsystems</div>
          <div className="flex flex-wrap gap-2">
            {subsystems.map(([name, count]) => (
              <span key={name} className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-2.5 py-1 text-xs text-cyan-300">
                {name} ({count})
              </span>
            ))}
          </div>
        </div>
      )}

      {(tab === "drift" && cochangePairs.length > 0) && (
        <div className="glass rounded-xl p-5">
          <div className="text-xs uppercase tracking-wider text-gray-500 mb-3">Top Co-Change Pairs</div>
          <div className="space-y-2 text-sm text-gray-300">
            {cochangePairs.slice(0, 8).map((pair) => (
              <div key={`${pair.pair.join("-")}-${pair.count}`} className="rounded-lg border border-t-border/30 bg-gray-950/35 px-3 py-2">
                {pair.pair.join(" ↔ ")} <span className="text-gray-500">({pair.count} commits)</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <ResultPanel result={current} loading={loading[tab]} />
    </div>
  );
}