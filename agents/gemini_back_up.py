"""Base agent class with Gemini API integration, retry, and structured output."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Optional

import structlog
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

from configs.settings import get_settings

logger = structlog.get_logger(__name__)


class BaseAgent:
    """Base class for all DQ platform agents with Gemini API integration."""

    def __init__(
        self,
        agent_name: str,
        system_prompt: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> None:
        settings = get_settings()
        self._name = agent_name
        self._system_prompt = system_prompt
        self._model = model or settings.gemini.model
        self._max_tokens = max_tokens or settings.gemini.max_tokens
        self._client = genai.Client(api_key=settings.gemini.api_key)
        self._log = logger.bind(agent=agent_name)

    async def _call_claude(
        self,
        prompt: str,
        context: Optional[dict[str, Any]] = None,
        stream: bool = False,
    ) -> str:
        """Call Gemini API, falling back through model list on 429 rate-limit errors."""
        content = prompt
        if context:
            context_str = json.dumps(context, indent=2, default=str)
            content = f"Context:\n{context_str}\n\n{prompt}"

        settings = get_settings()
        models_to_try = [self._model] + [
            m for m in settings.gemini.fallback_models if m != self._model
        ]

        last_exc: Exception | None = None
        for attempt, model in enumerate(models_to_try):
            try:
                self._log.info("calling_gemini", model=model, prompt_preview=prompt[:100])
                start = time.monotonic()
                response = await self._client.aio.models.generate_content(
                    model=model,
                    contents=content,
                    config=types.GenerateContentConfig(
                        system_instruction=self._system_prompt,
                        max_output_tokens=self._max_tokens,
                    ),
                )
                duration = time.monotonic() - start
                self._log.info("gemini_response_received", model=model,
                               duration_seconds=round(duration, 2))
                # Filter out thinking parts (gemini-2.5-* thinking models include
                # thought=True parts that must not be mixed into the response text).
                parts = response.candidates[0].content.parts
                text = "".join(
                    p.text for p in parts if not getattr(p, "thought", False) and p.text
                )
                return text or response.text
            except Exception as exc:
                exc_str = str(exc)
                if any(k in exc_str for k in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE")):
                    self._log.warning("gemini_unavailable", model=model, trying_next=True,
                                      error=exc_str[:120])
                    last_exc = exc
                    # Brief wait before trying next model to let transient overloads clear
                    await asyncio.sleep(2)
                    continue
                raise

        raise last_exc or RuntimeError("All Gemini models exhausted")

    async def _call_claude_json(
        self, prompt: str, context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Call Gemini and parse JSON from the response."""
        raw = await self._call_claude(prompt, context)
        return self._extract_json(raw)

    def _extract_json(self, text: str) -> dict[str, Any]:
        """Extract and parse the first JSON object or array from text."""
        import re

        if not text:
            return {"error": "Empty response from model"}

        text = text.strip()

        # 1. Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 2. Markdown code fence  (```json ... ```)
        json_block = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
        if json_block:
            try:
                return json.loads(json_block.group(1))
            except json.JSONDecodeError:
                pass

        # 3. Find the outermost { ... } object (handles preamble text)
        start = text.find("{")
        if start != -1:
            # Walk backwards from end to find matching closing brace
            depth = 0
            end = -1
            for i in range(len(text) - 1, start - 1, -1):
                if text[i] == "}":
                    depth += 1
                elif text[i] == "{":
                    depth -= 1
                if depth == 0:
                    end = i
                    break
            if end != -1:
                candidate = text[start : end + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass

        # 4. Array fallback
        arr_match = re.search(r"\[[\s\S]*\]", text)
        if arr_match:
            try:
                result = json.loads(arr_match.group())
                return {"items": result}
            except json.JSONDecodeError:
                pass

        self._log.error("json_parse_failed", raw_text=text[:500])
        return {"error": "Failed to parse JSON from Gemini response", "raw": text[:500]}
