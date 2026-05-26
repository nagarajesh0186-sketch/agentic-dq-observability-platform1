"""Base agent class with Anthropic Claude API integration, retry, and structured output."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import anthropic
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from configs.settings import get_settings

logger = structlog.get_logger(__name__)

# Claude pricing per 1M tokens (as of 2026)
_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-5":            {"input": 3.00,  "output": 15.00},
    "claude-sonnet-4-20250514":     {"input": 3.00,  "output": 15.00},
    "claude-opus-4-5":              {"input": 15.00, "output": 75.00},
    "claude-3-5-sonnet-20241022":   {"input": 3.00,  "output": 15.00},
    "claude-haiku-4-5-20251001":    {"input": 0.80,  "output": 4.00},
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a Claude API call."""
    pricing = _PRICING.get(model, {"input": 3.00, "output": 15.00})
    return round(
        (input_tokens / 1_000_000) * pricing["input"]
        + (output_tokens / 1_000_000) * pricing["output"],
        6,
    )


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

    async def _log_token_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_seconds: float,
        prompt_preview: str = "",
    ) -> None:
        """Log token usage and estimated cost to BigQuery dq_token_usage table."""
        try:
            from tools.bigquery.client import get_bq_client
            settings = get_settings()
            bq = get_bq_client()
            table_id = f"{settings.gcp.project_id}.{settings.gcp.dq_dataset}.dq_token_usage"

            cost_usd = _estimate_cost(model, input_tokens, output_tokens)

            rows = [{
                "usage_id": f"usage_{uuid.uuid4().hex[:12]}",
                "agent_name": self._name,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "estimated_cost_usd": cost_usd,
                "duration_seconds": round(duration_seconds, 3),
                "prompt_preview": prompt_preview[:200] if prompt_preview else "",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }]
            await bq.insert_rows(table_id, rows)
            self._log.info(
                "token_usage_logged",
                agent=self._name,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
            )
        except Exception as exc:
            self._log.warning("token_usage_log_failed", error=str(exc)[:200])

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
        models_to_try = [self._model] + [
            m for m in getattr(settings.anthropic, "fallback_models", [])
            if m != self._model
        ]

        last_exc: Exception | None = None
        for attempt, model in enumerate(models_to_try):
            try:
                self._log.info("calling_claude", model=model, prompt_preview=prompt[:100])
                start = time.monotonic()

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
                input_tokens  = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                cost_usd      = _estimate_cost(model, input_tokens, output_tokens)

                self._log.info(
                    "claude_response_received",
                    model=model,
                    duration_seconds=round(duration, 2),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost_usd=cost_usd,
                )

                # Log token usage to BigQuery asynchronously (non-blocking)
                asyncio.create_task(
                    self._log_token_usage(
                        model=model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        duration_seconds=duration,
                        prompt_preview=prompt[:200],
                    )
                )

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

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        json_block = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
        if json_block:
            try:
                return json.loads(json_block.group(1))
            except json.JSONDecodeError:
                pass

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

        arr_match = re.search(r"\[[\s\S]*\]", text)
        if arr_match:
            try:
                result = json.loads(arr_match.group())
                return {"items": result}
            except json.JSONDecodeError:
                pass

        self._log.error("json_parse_failed", raw_text=text[:500])
        return {"error": "Failed to parse JSON from Claude response", "raw": text[:500]}