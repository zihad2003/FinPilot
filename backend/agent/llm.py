"""OpenAI-compatible client. A missing key or a failed call never takes the app down."""

import json
import os

from app.config import settings


class LLMUnavailable(Exception):
    pass


def _tool_call_dict(call) -> dict:
    """Keep Gemini thought_signature / extra_content so the next turn is valid."""
    if hasattr(call, "model_dump"):
        dumped = call.model_dump(exclude_none=True)
    elif isinstance(call, dict):
        dumped = dict(call)
    else:
        dumped = {
            "id": getattr(call, "id", None),
            "type": "function",
            "function": {
                "name": getattr(getattr(call, "function", None), "name", None),
                "arguments": getattr(getattr(call, "function", None), "arguments", "{}"),
            },
        }
    function = dumped.get("function") or {}
    raw_args = function.get("arguments") or "{}"
    try:
        arguments = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
    except json.JSONDecodeError:
        arguments = {}
    item = {
        "id": dumped.get("id") or function.get("name"),
        "name": function.get("name"),
        "arguments": arguments,
        "raw": dumped,
    }
    if dumped.get("extra_content") is not None:
        item["extra_content"] = dumped["extra_content"]
    return item


class LLMClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self.base_url = base_url or settings.llm_base_url
        self.model = model or settings.llm_model
        self.sent: list[dict] = []

    def available(self) -> bool:
        if os.getenv("FINPILOT_DISABLE_LLM") == "1":
            return False
        return bool(self.api_key)

    def complete(self, messages: list[dict], tools: list[dict] | None) -> dict:
        self.sent.append({"messages": messages, "tools": [tool["function"]["name"] for tool in tools or []]})
        if not self.available():
            raise LLMUnavailable("The assistant is not configured.")
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools or None,
                temperature=0.2,
            )
        except Exception as exc:
            raise LLMUnavailable("The model call failed.") from exc
        message = response.choices[0].message
        tool_calls = [_tool_call_dict(call) for call in message.tool_calls or []]
        raw_assistant = None
        if hasattr(message, "model_dump"):
            raw_assistant = message.model_dump(exclude_none=True)
            # OpenAI SDK may omit provider extras; merge preserved tool call raw payloads.
            if tool_calls and raw_assistant.get("tool_calls"):
                merged = []
                for original, parsed in zip(raw_assistant["tool_calls"], tool_calls):
                    merged.append(parsed.get("raw") or original)
                raw_assistant["tool_calls"] = merged
        return {
            "content": message.content or "",
            "tool_calls": tool_calls,
            "raw_assistant": raw_assistant,
        }

    def categorize_merchant(self, merchant_key: str) -> str:
        if not self.available():
            return "other"
        try:
            result = self.complete(
                [
                    {
                        "role": "system",
                        "content": (
                            "Classify the merchant key into one category: "
                            "income, housing, groceries, transport, subscriptions, utilities, "
                            "education, dining, shopping, savings, other. Reply with the category only."
                        ),
                    },
                    {"role": "user", "content": merchant_key},
                ],
                tools=None,
            )
        except LLMUnavailable:
            return "other"
        text = (result.get("content") or "").strip().lower()
        return text.split()[0] if text else "other"


class FakeLLM:
    """Scripted model for tests. Never touches the network."""

    def __init__(self, steps: list[dict] | None = None, available: bool = True):
        self.steps = list(steps or [])
        self._available = available
        self.sent: list[dict] = []

    def available(self) -> bool:
        return self._available

    def complete(self, messages: list[dict], tools: list[dict] | None) -> dict:
        self.sent.append(
            {
                "messages": messages,
                "tools": [tool["function"]["name"] for tool in tools or []],
            }
        )
        if not self._available:
            raise LLMUnavailable("disabled")
        if not self.steps:
            return {"content": "I could not find more to add.", "tool_calls": [], "raw_assistant": None}
        step = self.steps.pop(0)
        return {
            "content": step.get("content") or "",
            "tool_calls": step.get("tool_calls") or [],
            "raw_assistant": step.get("raw_assistant"),
        }

    def categorize_merchant(self, merchant_key: str) -> str:
        self.sent.append({"messages": [{"role": "user", "content": merchant_key}], "tools": []})
        if self.steps:
            step = self.steps.pop(0)
            return step.get("category") or step.get("content") or "other"
        return "groceries"


def build_llm_from_settings() -> LLMClient:
    return LLMClient()
