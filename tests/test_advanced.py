from __future__ import annotations

import subprocess
from pathlib import Path

from trace_engine.core import Trace
from trace_engine.models.code_graph import CodeGraph
from trace_engine.query.advanced import AdvancedAnalyzer
from trace_engine.query.llm import TraceLLMClient


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
        rankings = result.metadata.get("rankings")
        assert rankings
        assert all("fan_in" in item and "fan_out" in item for item in rankings)

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

    def test_refactor_plan_returns_candidates(self, sample_graph: CodeGraph):
        analyzer = AdvancedAnalyzer(sample_graph, repo_root=FIXTURES_DIR)
        result = analyzer.refactor_plan()

        assert result.evidence

    def test_ask_architecture_reports_missing_llm_config(self, sample_graph: CodeGraph, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("TRACE_LLM_API_KEY", raising=False)
        analyzer = AdvancedAnalyzer(sample_graph, repo_root=FIXTURES_DIR)
        result = analyzer.ask_architecture("Where is auth implemented?")

        assert "not configured" in result.conclusion.lower()
        assert result.metadata.get("ui_blocks")

    def test_ask_architecture_builds_structured_ui_from_llm(self, sample_graph: CodeGraph, monkeypatch):
        class FakeClient:
            def complete_structured_with_tools(self, **kwargs):
                tool_handler = kwargs["tool_handler"]
                tool_handler("get_repo_overview", {})
                tool_handler("find_concept_matches", {"concept": "auth", "limit": 3})
                return {
                    "summary": "Authentication is centered in the API and service layers.",
                    "confidence": "high",
                    "reasoning_steps": [
                        "Checked the repo overview for major subsystems.",
                        "Looked up concept matches for auth-related symbols.",
                    ],
                    "ui_blocks": [
                        {
                            "type": "narrative",
                            "title": "Answer",
                            "body": "Authentication is centered in the API and service layers.",
                            "tone": "info",
                            "items": [],
                        },
                        {
                            "type": "files",
                            "title": "Relevant Files",
                            "body": "Primary implementation points.",
                            "tone": "info",
                            "items": [
                                {
                                    "label": "AuthService",
                                    "value": "services/auth.py",
                                    "description": "Core authentication service logic.",
                                }
                            ],
                        },
                    ],
                    "citations": [
                        {
                            "file_path": "services/auth.py",
                            "label": "AuthService",
                            "summary": "Core authentication service logic.",
                        }
                    ],
                }

        monkeypatch.setattr(TraceLLMClient, "from_environment", classmethod(lambda cls: FakeClient()))
        analyzer = AdvancedAnalyzer(sample_graph, repo_root=FIXTURES_DIR)

        result = analyzer.ask_architecture("Where is auth implemented?")

        assert result.conclusion == "Authentication is centered in the API and service layers."
        assert result.metadata.get("ui_blocks")
        assert result.metadata.get("tool_trace")
        assert any(evidence.file_path == "services/auth.py" for evidence in result.evidence)

    def test_ask_architecture_passes_short_query_to_llm(self, sample_graph: CodeGraph, monkeypatch):
        class FakeClient:
            def complete_structured_with_tools(self, **kwargs):
                assert "Question: hi" in kwargs["user_prompt"]
                return {
                    "summary": "Hello. Ask a repository question whenever you're ready.",
                    "confidence": "high",
                    "reasoning_steps": [],
                    "ui_blocks": [
                        {
                            "type": "narrative",
                            "title": "Greeting",
                            "body": "Hello. Ask a repository question whenever you're ready.",
                            "tone": "info",
                            "items": [],
                        }
                    ],
                    "citations": [],
                }

        monkeypatch.setattr(TraceLLMClient, "from_environment", classmethod(lambda cls: FakeClient()))
        analyzer = AdvancedAnalyzer(sample_graph, repo_root=FIXTURES_DIR)

        result = analyzer.ask_architecture("hi")

        assert result.conclusion == "Hello. Ask a repository question whenever you're ready."
        assert result.metadata.get("ui_blocks")


def test_trace_llm_client_reads_openai_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("TRACE_LLM_API_KEY", raising=False)

    client = TraceLLMClient.from_environment()

    assert client._api_key == "test-key"


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


def test_pr_review_uses_git_refs(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "trace@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Trace Test"], cwd=repo, check=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo, check=True, capture_output=True)

    app_file = repo / "app.py"
    app_file.write_text("def main():\n    return 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    subprocess.run(["git", "checkout", "-b", "feature/review"], cwd=repo, check=True, capture_output=True)
    app_file.write_text("def main():\n    return 2\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-am", "update app"], cwd=repo, check=True, capture_output=True)

    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "clone", "--bare", str(repo), str(bare)], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "main", "feature/review"], cwd=repo, check=True, capture_output=True)

    resolved_repo = tmp_path / "clone"
    subprocess.run(["git", "clone", "--depth", "1", "--branch", "feature/review", str(bare), str(resolved_repo)], cwd=tmp_path, check=True, capture_output=True)

    trace = Trace(resolved_repo, source=str(bare), ref="feature/review")
    trace.ingest()
    result = trace.pr_review(base_ref="main", head_ref="feature/review")

    assert "app.py" in result.metadata.get("changed_files", [])
    assert result.metadata.get("risk_level") in {"low", "medium", "high"}
    assert result.metadata.get("risk_reasons")


def test_pr_review_ignores_refs_that_git_would_read_as_options(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "trace@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Trace Test"], cwd=repo, check=True)

    app_file = repo / "app.py"
    app_file.write_text("def main():\n    return 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    app_file.write_text("def main():\n    return 2\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-am", "update app"], cwd=repo, check=True, capture_output=True)

    trace = Trace(repo)
    trace.ingest()
    written_by_git = tmp_path / "written-by-git.txt"
    result = trace.pr_review(base_ref=f"--output={written_by_git}", head_ref="HEAD")

    assert not written_by_git.exists()
    assert "changed_files" not in result.metadata
