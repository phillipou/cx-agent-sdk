from __future__ import annotations
"""OpenAI LLM provider.

Implements the `LLMProvider` interface using OpenAI's Responses API. The
classifier expects a structured JSON-like dict with keys:

    {"intent_id": str | None, "params": dict, "missing_params": list, "confidence": float}

We prompt the model to return a strict JSON object. Consumers set the API key
via the `OPENAI_API_KEY` environment variable. The model should be chosen
programmatically per agent/function by passing `model=...` to the constructor;
an `OPENAI_MODEL` env var is supported as a fallback only.
"""

import os
from typing import Any, Dict, List

try:
    # OpenAI Python SDK >= 1.0
    from openai import OpenAI  # type: ignore
except Exception as e:  # pragma: no cover - import-time guard
    OpenAI = None  # type: ignore

from src.core.interfaces import LLMProvider


class OpenAIProvider(LLMProvider):
    """Concrete LLM provider for OpenAI.

    - Uses JSON mode to get a machine-parseable response.
    - Does not inject business logic; only forwards prompts and returns the
      parsed dict.
    """

    def __init__(self, model: str | None = None) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAIProvider")
        if OpenAI is None:
            raise RuntimeError(
                "openai package not available. Install 'openai>=1.0.0' to use OpenAIProvider."
            )
        self.client = OpenAI()
        # Prefer explicit per-agent model; fall back to env; then to a safe default.
        self.model = model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"

    def generate(self, messages: List[Dict[str, Any]], response_format: Dict | None = None) -> dict:
        """Call the OpenAI Responses API and return a dict.

        Parameters
        - messages: List of chat messages with roles {"system"|"user"|"assistant"}.
        - response_format: When provided, we request JSON mode.

        Returns
        - dict: Parsed JSON object according to the classifier contract.
        """
        # Convert chat-style messages into the responses API input. We pass the
        # content as-is; if `response_format` signals JSON, request JSON mode.
        # The prompt (provided by the classifier) must instruct the model to
        # produce the expected JSON keys.
        force_json = bool(response_format)

        # Build a single string with role-tagged content for simplicity.
        # Alternatively, one could map to the SDK's message parts structure.
        prompt_parts: List[str] = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            prompt_parts.append(f"[{role}]\n{content}")
        prompt = "\n\n".join(prompt_parts)

        resp = self.client.responses.create(
            model=self.model,
            input=prompt,
            response_format={"type": "json_object"} if force_json else None,
        )

        # Extract the text content and parse JSON via SDK's convenience field.
        # In JSON mode, `output_parsed` contains the parsed object.
        if getattr(resp, "output_parsed", None):  # type: ignore[attr-defined]
            return resp.output_parsed  # type: ignore[attr-defined]

        # Fallback: try to read the first text block (non-JSON mode).
        # The caller (classifier) should guard against malformed outputs.
        text = None
        try:
            text = resp.output[0].content[0].text  # type: ignore[attr-defined]
        except Exception:
            pass
        return {"raw": text}

    def route(self, interaction, history):  # pragma: no cover - unused
        """Compatibility stub; not used in the current design."""
        return {"tool_name": "", "params": {}}
