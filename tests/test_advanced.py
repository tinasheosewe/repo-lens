from __future__ import annotations

import subprocess
from pathlib import Path

from trace_engine.core import Trace
from trace_engine.models.code_graph import CodeGraph
from trace_engine.query.advanced import AdvancedAnalyzer


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sample_project"


class TestAdvancedAnalyzer:
    def test_finds_stale_modules(self, sample_graph: CodeGraph):
        analyzer = AdvancedAnalyzer(sample_graph, repo_root=FIXTURES_DIR)
        result = analyzer.find_stale_modules()

        stale_files = {e.file_path for e in result.evidence}
        assert "utils/helpers.py" in stale_files or "utils/validators.py" in stale_files

    def test_traces_route_entry_flows(self, sample_graph: CodeGraph):
        analyzer = AdvancedAnalyzer(sample_graph, repo_root=FIXTURES_DIR)
        result = analyzer.trace_entry_flows(kind="route", max_depth=4)

        assert result.metadata.get("path_details")
        assert any("ROUTE" in evidence.description for evidence in result.evidence)

    def test_ranks_critical_symbols(self, sample_graph: CodeGraph):
        analyzer = AdvancedAnalyzer(sample_graph, repo_root=FIXTURES_DIR)
        result = analyzer.rank_criticality(limit=5)

        names = {e.function_name for e in result.evidence}
        assert "authenticate" in names or "process_payment" in names

    def test_onboarding_summary_has_subsystems(self, sample_graph: CodeGraph):
        analyzer = AdvancedAnalyzer(sample_graph, repo_root=FIXTURES_DIR)
        result = analyzer.onboarding_summary()

        subsystems = result.metadata.get("subsystems")
        assert subsystems
        assert any(name in {"api", "services", "utils", "root"} for name, _count in subsystems)

    def test_concept_search_finds_services(self, sample_graph: CodeGraph):
        analyzer = AdvancedAnalyzer(sample_graph, repo_root=FIXTURES_DIR)
        result = analyzer.concept_search("service")

        assert any(e.function_name == "AuthService" or e.function_name == "PaymentService" for e in result.evidence)

    def test_call_flow_returns_paths(self, sample_graph: CodeGraph):
        analyzer = AdvancedAnalyzer(sample_graph, repo_root=FIXTURES_DIR)
        result = analyzer.call_flow("create_payment", max_depth=4)

        assert result.metadata.get("path_details")

    def test_pr_review_uses_changed_files(self, sample_graph: CodeGraph):
        analyzer = AdvancedAnalyzer(sample_graph, repo_root=FIXTURES_DIR)
        result = analyzer.pr_review(changed_files=["services/auth.py"])

        assert "services/auth.py" in result.metadata.get("changed_files", [])

    def test_refactor_plan_returns_candidates(self, sample_graph: CodeGraph):
        analyzer = AdvancedAnalyzer(sample_graph, repo_root=FIXTURES_DIR)
        result = analyzer.refactor_plan()

        assert result.evidence

    def test_migration_tracker_finds_term_hits(self, sample_graph: CodeGraph):
        analyzer = AdvancedAnalyzer(sample_graph, repo_root=FIXTURES_DIR)
        result = analyzer.migration_tracker(legacy_terms=["AuthService"], target_term="IdentityService")

        assert result.metadata.get("legacy_hits", 0) > 0

    def test_ask_architecture_reports_missing_llm_config(self, sample_graph: CodeGraph, monkeypatch):
        monkeypatch.delenv("TRACE_LLM_API_KEY", raising=False)
        analyzer = AdvancedAnalyzer(sample_graph, repo_root=FIXTURES_DIR)
        result = analyzer.ask_architecture("Where is auth implemented?")

        assert "not configured" in result.conclusion.lower()


def test_history_drift_on_git_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "trace@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Trace Test"], cwd=repo, check=True)

    app_file = repo / "app.py"
    helper_file = repo / "helper.py"
    app_file.write_text("def main():\n    return 1\n", encoding="utf-8")
    helper_file.write_text("def helper():\n    return 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    app_file.write_text("def main():\n    return 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "update app"], cwd=repo, check=True, capture_output=True)

    trace = Trace(repo)
    trace.ingest()
    result = trace.history_drift(limit=5)

    assert result.evidence
    assert any(e.file_path == "app.py" for e in result.evidence)