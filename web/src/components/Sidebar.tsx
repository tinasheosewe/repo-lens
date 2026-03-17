import {
  AlertTriangle,
  BookOpen,
  Compass,
  GitBranch,
  LayoutDashboard,
  Milestone,
  Radio,
  Route,
  Search,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import type { Page, StatusResponse } from "../types";

const NAV_ITEMS: { id: Page; label: string; description: string; icon: React.ReactNode }[] = [
  { id: "about", label: "About", description: "Load repos and inspect support boundaries.", icon: <BookOpen size={18} /> },
  { id: "discovery", label: "Discovery", description: "Onboarding, concept search, Q&A, and repo drift.", icon: <Search size={18} /> },
  { id: "dashboard", label: "Dashboard", description: "High-level graph, language, and asset overview.", icon: <LayoutDashboard size={18} /> },
  { id: "audit", label: "Audit", description: "Stale modules and criticality ranking.", icon: <ShieldCheck size={18} /> },
  { id: "flows", label: "Flows", description: "Trace entry points and execution paths.", icon: <Route size={18} /> },
  { id: "workflow", label: "Workflow", description: "PR review, refactors, and engineering workflows.", icon: <Milestone size={18} /> },
  { id: "impact", label: "Impact Analysis", description: "See what depends on a selected change.", icon: <Radio size={18} /> },
  { id: "dead-code", label: "Dead Code", description: "Find unreachable or unused graph nodes.", icon: <Trash2 size={18} /> },
  { id: "dependencies", label: "Dependencies", description: "Inspect coupling, cycles, and hotspots.", icon: <GitBranch size={18} /> },
  { id: "explorer", label: "Explorer", description: "Find graph paths between symbols.", icon: <Compass size={18} /> },
];

interface Props {
  activePage: Page;
  onNavigate: (page: Page) => void;
  status: StatusResponse | null;
}

export default function Sidebar({ activePage, onNavigate, status }: Props) {
  const repoLabel = status?.repo_display_source
    ? status.repo_display_source.replace(/\.git$/, "").split("/").filter(Boolean).pop()
    : null;

  return (
    <aside className="w-72 h-full min-h-0 overflow-hidden flex flex-col border-r border-t-border bg-t-surface shrink-0">
      {/* Logo */}
      <div className="px-5 py-6 flex items-center gap-2.5">
        <img
          src="/trace-icon.svg"
          alt="Trace"
          className="h-10 w-10 shrink-0 rounded-xl border border-white/10 bg-[#090B16] p-1 shadow-[0_0_24px_rgba(129,140,248,0.18)]"
        />
        <div>
          <span className="block text-lg font-bold tracking-tight gradient-text">
            Trace
          </span>
          <span className="block text-[11px] uppercase tracking-[0.22em] text-gray-500">
            RepoLens
          </span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 min-h-0 overflow-y-auto px-3 space-y-0.5 pb-3">
        {NAV_ITEMS.map(({ id, label, description, icon }) => {
          const active = activePage === id;
          return (
            <button
              key={id}
              onClick={() => onNavigate(id)}
              className={`
                w-full flex items-start gap-3 px-3 py-3 rounded-lg text-left
                transition-all duration-150
                ${
                  active
                    ? "bg-t-primary/10 text-t-primary-light"
                    : "text-gray-400 hover:text-gray-200 hover:bg-t-hover"
                }
              `}
            >
              <span className="mt-0.5">{icon}</span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium">{label}</span>
                <span className={`mt-0.5 block text-[11px] leading-relaxed ${active ? "text-t-primary/80" : "text-gray-500"}`}>
                  {description}
                </span>
              </span>
              {active && (
                <span className="mt-1 ml-auto w-1.5 h-1.5 rounded-full bg-t-primary animate-glow-pulse" />
              )}
            </button>
          );
        })}
      </nav>

      {/* Status pill */}
      <div className="shrink-0 px-4 py-4 border-t border-t-border bg-t-surface">
        {status?.loaded ? (
          <div className="text-xs space-y-1.5">
            <div className="flex items-center gap-1.5 text-t-emerald">
              <span className="w-1.5 h-1.5 rounded-full bg-t-emerald" />
              Connected
            </div>
            <div className="text-gray-500 font-mono truncate" title={status.repo_display_source ?? status.repo_path ?? ""}>
              {repoLabel}
            </div>
            <div className="text-gray-500">
              {status.node_count} nodes · {status.edge_count} edges
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 text-xs text-t-amber">
            <AlertTriangle size={12} />
            No repo loaded
          </div>
        )}
      </div>
    </aside>
  );
}
