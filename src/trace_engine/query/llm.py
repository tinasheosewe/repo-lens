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
        api_key = os.getenv("TRACE_LLM_API_KEY")
        if not api_key:
            raise LLMConfigurationError(
                "TRACE_LLM_API_KEY is not configured."
            )
        model = os.getenv("TRACE_LLM_MODEL", "gpt-4.1-mini")
        base_url = os.getenv("TRACE_LLM_BASE_URL", "https://api.openai.com/v1")
        return cls(api_key=api_key, model=model, base_url=base_url)

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
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
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM request failed: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"LLM request failed: {exc.reason}") from exc

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("LLM request returned no choices.")
        message = choices[0].get("message") or {}
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
        raise RuntimeError("LLM response content was empty.")