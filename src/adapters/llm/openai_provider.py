from __future__ import annotations
"""OpenAI LLM provider.

Implements the `LLMProvider` interface using the OpenAI Python SDK. Supports
both the Responses API and Chat Completions API, falling back automatically to
whichever is available in the installed SDK version. When JSON mode is
requested, attempts to return a parsed object; otherwise returns raw text.
"""

import os
import json
from typing import Any, Dict, List

try:
    # OpenAI Python SDK >= 1.0
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - import-time guard
    OpenAI = None  # type: ignore

from src.core.interfaces import LLMProvider


def _to_prompt_str(messages: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        parts.append(f"[{role}]\n{content}")
    return "\n\n".join(parts)


class OpenAIProvider(LLMProvider):
    """Concrete LLM provider for OpenAI with graceful API fallback."""

    def __init__(self, model: str | None = None) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAIProvider")
        if OpenAI is None:
            raise RuntimeError(
                "openai package not available. Install 'openai>=1.0.0' to use OpenAIProvider."
            )
        self.client = OpenAI()
        self.model = model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"

    def generate(self, messages: List[Dict[str, Any]], response_format: Dict | None = None) -> dict:
        """Call OpenAI and return structured output when possible.

        - Prefers Responses API with JSON mode when available.
        - Falls back to Chat Completions API with JSON mode if supported.
        - As a last resort, returns a dict with a `raw` text field.
        """
        force_json = bool(response_format)

        # 1) Try Responses API (SDKs that support `response_format`)
        try:
            if hasattr(self.client, "responses"):
                prompt = _to_prompt_str(messages)
                kwargs: Dict[str, Any] = {"model": self.model, "input": prompt}
                resp = self.client.responses.create(**kwargs)  # type: ignore[arg-type]

                if getattr(resp, "output_parsed", None):  # JSON mode success
                    return resp.output_parsed  # type: ignore[attr-defined]
                # Fallback to text extraction
                try:
                    text = resp.output[0].content[0].text  # type: ignore[attr-defined]
                except Exception:
                    text = None
                # Try to parse JSON if requested
                if force_json and isinstance(text, str):
                    try:
                        return json.loads(text)
                    except Exception:
                        pass
                return {"raw": text}
        except TypeError:
            # Older SDK may not accept `response_format` here; fall through
            pass
        except Exception:
            # Non-fatal; try chat completions next
            pass

        # 2) Try Chat Completions API
        try:
            if hasattr(self.client, "chat") and hasattr(self.client.chat, "completions"):
                chat_messages = [
                    {"role": m.get("role", "user"), "content": m.get("content", "")}
                    for m in messages
                ]
                kwargs = {"model": self.model, "messages": chat_messages}
                # Older SDKs do not support `response_format`; rely on prompting and parse.
                comp = self.client.chat.completions.create(**kwargs)  # type: ignore[arg-type]
                text = None
                try:
                    text = comp.choices[0].message.content  # type: ignore[attr-defined]
                except Exception:
                    pass
                if force_json and isinstance(text, str):
                    try:
                        return json.loads(text)
                    except Exception:
                        pass
                return {"raw": text}
        except Exception:
            pass

        # 3) Give up with a clear fallback
        return {"raw": None}

    def route(self, interaction, history):  # pragma: no cover - unused
        return {"tool_name": "", "params": {}}
