from __future__ import annotations

import json
import os
from urllib import error, request


class LLMConfigurationError(RuntimeError):
    """Raised when Trace LLM settings are missing."""


class TraceLLMClient:
    """Minimal OpenAI-compatible chat client configured via environment variables."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")

    @classmethod
    def from_environment(cls) -> TraceLLMClient:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("TRACE_LLM_API_KEY")
        if not api_key:
            raise LLMConfigurationError(
                "OPENAI_API_KEY or TRACE_LLM_API_KEY is not configured."
            )
        model = os.getenv("TRACE_LLM_MODEL", "gpt-4.1-mini")
        base_url = os.getenv("TRACE_LLM_BASE_URL", "https://api.openai.com/v1")
        return cls(api_key=api_key, model=model, base_url=base_url)

    def _send_chat_request(self, payload: dict[str, object]) -> dict[str, object]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self._base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=45) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM request failed: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"LLM request failed: {exc.reason}") from exc

    @staticmethod
    def _message_text(message: dict[str, object]) -> str:
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict)
            ]
            return "\n".join(part for part in parts if part).strip()
        return ""

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        data = self._send_chat_request(payload)

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("LLM request returned no choices.")
        message = choices[0].get("message") or {}
        text = self._message_text(message)
        if text:
            return text
        raise RuntimeError("LLM response content was empty.")

    def complete_structured_with_tools(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict[str, object],
        tools: list[dict[str, object]],
        tool_handler,
        max_round_trips: int = 6,
    ) -> dict[str, object]:
        messages: list[dict[str, object]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        for _round_trip in range(max_round_trips):
            payload: dict[str, object] = {
                "model": self._model,
                "messages": messages,
                "temperature": 0.2,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "trace_ui_answer",
                        "strict": True,
                        "schema": response_schema,
                    },
                },
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            data = self._send_chat_request(payload)
            choices = data.get("choices") or []
            if not choices:
                raise RuntimeError("LLM request returned no choices.")

            message = choices[0].get("message") or {}
            tool_calls = message.get("tool_calls") or []
            if tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": message.get("content") or "",
                        "tool_calls": tool_calls,
                    }
                )
                for tool_call in tool_calls:
                    call_id = tool_call.get("id", "")
                    function = tool_call.get("function") or {}
                    name = function.get("name", "")
                    raw_args = function.get("arguments") or "{}"
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else {}
                    except json.JSONDecodeError:
                        args = {}

                    try:
                        result = tool_handler(name, args)
                    except Exception as exc:  # pragma: no cover - defensive fallback
                        result = {"error": str(exc)}

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": json.dumps(result),
                        }
                    )
                continue

            text = self._message_text(message)
            if not text:
                raise RuntimeError("LLM response content was empty.")
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise RuntimeError("LLM structured response was not valid JSON.") from exc
            if not isinstance(parsed, dict):
                raise RuntimeError("LLM structured response must be a JSON object.")
            return parsed

        raise RuntimeError("LLM tool execution exceeded the maximum number of round trips.")