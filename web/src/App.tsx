import { useEffect, useState } from "react";
import type { Page, StatusResponse } from "./types";
import { api } from "./api/client";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import Impact from "./pages/Impact";
import DeadCode from "./pages/DeadCode";
import Dependencies from "./pages/Dependencies";
import Explorer from "./pages/Explorer";

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .status()
      .then(setStatus)
      .catch(() => setStatus(null))
      .finally(() => setLoading(false));
  }, []);

  const refresh = () => {
    api.status().then(setStatus).catch(() => {});
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center animate-fade-in">
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
          {page === "dashboard" && <Dashboard />}
          {page === "impact" && <Impact />}
          {page === "dead-code" && <DeadCode />}
          {page === "dependencies" && <Dependencies />}
          {page === "explorer" && <Explorer />}
        </div>
      </main>
    </div>
  );
}
