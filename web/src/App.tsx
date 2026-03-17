import { useEffect, useState } from "react";
import type { Page, StatusResponse } from "./types";
import { api } from "./api/client";
import Sidebar from "./components/Sidebar";
import About from "./pages/About";
import Audit from "./pages/Audit";
import Dashboard from "./pages/Dashboard";
import Discovery from "./pages/Discovery";
import Flows from "./pages/Flows";
import Impact from "./pages/Impact";
import DeadCode from "./pages/DeadCode";
import Dependencies from "./pages/Dependencies";
import Explorer from "./pages/Explorer";
import Workflow from "./pages/Workflow";

export default function App() {
  const [page, setPage] = useState<Page>("about");
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .status()
      .then((nextStatus) => {
        setStatus(nextStatus);
        setPage(nextStatus.loaded ? "dashboard" : "about");
      })
      .catch(() => setStatus(null))
      .finally(() => setLoading(false));
  }, []);

  const handleRepoLoaded = (nextStatus: StatusResponse) => {
    setStatus(nextStatus);
    setPage("dashboard");
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center animate-fade-in">
          <img
            src="/trace-icon.svg"
            alt="Trace"
            className="mx-auto mb-4 h-16 w-16 rounded-2xl border border-white/10 bg-[#090B16] p-2 shadow-[0_0_40px_rgba(129,140,248,0.22)]"
          />
          <h1 className="text-3xl font-bold gradient-text mb-2">Trace</h1>
          <p className="text-gray-500 text-sm">Loading…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      <Sidebar activePage={page} onNavigate={setPage} status={status} />
      <main className="flex-1 overflow-y-auto">
        <div className="p-8 max-w-[1400px] mx-auto">
          {page === "about" && <About status={status} onRepoLoaded={handleRepoLoaded} />}
          {page === "discovery" && <Discovery />}
          {page === "dashboard" && <Dashboard />}
          {page === "audit" && <Audit />}
          {page === "flows" && <Flows />}
          {page === "workflow" && <Workflow status={status} />}
          {page === "impact" && <Impact />}
          {page === "dead-code" && <DeadCode />}
          {page === "dependencies" && <Dependencies />}
          {page === "explorer" && <Explorer />}
        </div>
      </main>
    </div>
  );
}
