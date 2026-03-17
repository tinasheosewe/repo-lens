from __future__ import annotations

from collections.abc import Iterable

from trace_engine.analysis.base_parser import BaseParser

from .css_parser import CssParser
from .ecmascript_parser import JavaScriptParser, TypeScriptParser
from .html_parser import HtmlParser
from .python_parser import PythonParser


class ParserRegistry:
    """Registry of all language parsers known to Trace."""

    def __init__(self, parsers: list[BaseParser] | None = None) -> None:
        self._parsers = tuple(
            parsers
            or [
                PythonParser(),
                JavaScriptParser(),
                TypeScriptParser(),
                HtmlParser(),
                CssParser(),
            ]
        )
        self._parsers_by_language = {
            parser.language_name(): parser for parser in self._parsers
        }

    @property
    def parsers(self) -> tuple[BaseParser, ...]:
        return self._parsers

    @property
    def supported_languages(self) -> list[str]:
        return sorted(self._parsers_by_language)

    @property
    def supported_extensions(self) -> set[str]:
        extensions: set[str] = set()
        for parser in self._parsers:
            extensions.update(parser.supported_extensions())
        return extensions

    def detect_parsers(self, file_paths: Iterable[str]) -> tuple[BaseParser, ...]:
        file_list = tuple(file_paths)
        return tuple(
            parser
            for parser in self._parsers
            if parser.matches_repository(file_list)
        )

    def parsers_for_languages(
        self,
        languages: Iterable[str],
    ) -> tuple[BaseParser, ...]:
        return tuple(
            self._parsers_by_language[language]
            for language in languages
            if language in self._parsers_by_language
        )


DEFAULT_PARSER_REGISTRY = ParserRegistry()