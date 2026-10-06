"""Tests for the tree-sitter JavaScript and TypeScript parsers."""

from trace_engine.analysis.ecmascript_parser import TypeScriptParser
from trace_engine.models.graph import NodeType

TSX_COMPONENT = """\
import Explorer from "./pages/Explorer";
import { loadStatus } from "./api";

export default function App({ page }: { page: string }) {
  if (!page) {
    return <p>Loading</p>;
  }
  return (
    <main>
      {page === "explorer" && <Explorer status={loadStatus()} />}
    </main>
  );
}
"""


class TestTsx:
    def test_component_with_jsx_is_parsed(self):
        result = TypeScriptParser().parse_file("src/App.tsx", TSX_COMPONENT)

        functions = {node.name for node in result.nodes if node.node_type == NodeType.FUNCTION}
        assert functions == {"App"}
        assert result.exports["default"] == "src/App.tsx::App"

    def test_call_inside_jsx_is_recorded(self):
        result = TypeScriptParser().parse_file("src/App.tsx", TSX_COMPONENT)

        calls = {(call.caller_id, call.called_name) for call in result.unresolved_calls}
        assert ("src/App.tsx::App", "loadStatus") in calls
