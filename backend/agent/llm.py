"""OpenAI-compatible client. A missing key or a failed call never takes the app down."""

import json
import os

from app.config import settings


class LLMUnavailable(Exception):
    pass


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
        tool_calls = []
        for call in message.tool_calls or []:
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append({"id": call.id, "name": call.function.name, "arguments": arguments})
        return {"content": message.content or "", "tool_calls": tool_calls}

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
            return {"content": "I could not find more to add.", "tool_calls": []}
        step = self.steps.pop(0)
        return {
            "content": step.get("content") or "",
            "tool_calls": step.get("tool_calls") or [],
        }

    def categorize_merchant(self, merchant_key: str) -> str:
        self.sent.append({"messages": [{"role": "user", "content": merchant_key}], "tools": []})
        if self.steps:
            step = self.steps.pop(0)
            return step.get("category") or step.get("content") or "other"
        return "groceries"


def build_llm_from_settings() -> LLMClient:
    return LLMClient()
