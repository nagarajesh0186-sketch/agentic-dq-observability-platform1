"""Base agent class with Anthropic Claude API integration, retry, and structured output."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Optional

import anthropic
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from configs.settings import get_settings

logger = structlog.get_logger(__name__)


class BaseAgent:
    """Base class for all DQ platform agents with Anthropic Claude API integration."""

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
        self._model = model or settings.anthropic.model
        self._max_tokens = max_tokens or settings.anthropic.max_tokens
        self._client = anthropic.Anthropic(api_key=settings.anthropic.api_key)
        self._log = logger.bind(agent=agent_name)

    async def _call_claude(
        self,
        prompt: str,
        context: Optional[dict[str, Any]] = None,
        stream: bool = False,
    ) -> str:
        """Call Anthropic Claude API with retry on rate-limit / overload errors."""
        content = prompt
        if context:
            context_str = json.dumps(context, indent=2, default=str)
            content = f"Context:\n{context_str}\n\n{prompt}"

        settings = get_settings()
        # Build model list: primary first, then any fallbacks defined in settings
        models_to_try = [self._model] + [
            m for m in getattr(settings.anthropic, "fallback_models", [])
            if m != self._model
        ]

        last_exc: Exception | None = None
        for attempt, model in enumerate(models_to_try):
            try:
                self._log.info("calling_claude", model=model, prompt_preview=prompt[:100])
                start = time.monotonic()

                # Claude's SDK is sync; run in thread so we don't block the event loop
                response = await asyncio.to_thread(
                    self._client.messages.create,
                    model=model,
                    max_tokens=self._max_tokens,
                    system=self._system_prompt,
                    messages=[
                        {"role": "user", "content": content}
                    ],
                )

                duration = time.monotonic() - start
                self._log.info(
                    "claude_response_received",
                    model=model,
                    duration_seconds=round(duration, 2),
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                )

                # Extract text from the first text block
                text = "".join(
                    block.text for block in response.content
                    if block.type == "text"
                )
                return text

            except anthropic.RateLimitError as exc:
                self._log.warning("claude_rate_limit", model=model, trying_next=(attempt + 1 < len(models_to_try)), error=str(exc)[:120])
                last_exc = exc
                await asyncio.sleep(2)
                continue

            except anthropic.APIStatusError as exc:
                # 529 = overloaded, 503 = unavailable
                if exc.status_code in (503, 529):
                    self._log.warning("claude_unavailable", model=model, status=exc.status_code, trying_next=True, error=str(exc)[:120])
                    last_exc = exc
                    await asyncio.sleep(2)
                    continue
                raise

        raise last_exc or RuntimeError("All Claude models exhausted")

    async def _call_claude_json(
        self, prompt: str, context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Call Claude and parse JSON from the response."""
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
        return {"error": "Failed to parse JSON from Claude response", "raw": text[:500]}
