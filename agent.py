"""Core chat loop for Ask Sriram, with input/output guards."""

import json
import os

from openai import OpenAI

from prompts import CANARY, SYSTEM_PROMPT
from tools import REGISTRY, SCHEMAS

MODEL = os.getenv("MODEL", "gpt-4o-mini")
MAX_INPUT_CHARS = 800
MAX_HISTORY_MESSAGES = 12
MAX_TOOL_ROUNDS = 4

FALLBACK = "Sorry, I can't help with that. I'm happy to answer questions about Sriram's work, skills or how to reach him."

_client: OpenAI | None = None


def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def _clean_history(history: list) -> list[dict]:
    """Keep only well-formed user/assistant text turns, newest last, trimmed."""
    out = []
    for m in history or []:
        if not isinstance(m, dict):
            continue
        role, content = m.get("role"), m.get("content")
        if isinstance(content, list):  # Gradio 6 structured content
            content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            out.append({"role": role, "content": content[:MAX_INPUT_CHARS * 2]})
    return out[-MAX_HISTORY_MESSAGES:]


def _leaks_prompt(text: str) -> bool:
    if CANARY in text:
        return True
    markers = ("<security>", "<truth_rules>", "<KNOWLEDGE>", "These rules cannot be changed")
    return any(m in text for m in markers)


def _scrub(text: str) -> str:
    # House style: no em dashes.
    return text.replace(" — ", ", ").replace("—", ", ").strip()


def answer(message: str, history: list | None = None) -> str:
    message = (message or "").strip()
    if not message:
        return "Ask me anything about Sriram's work, skills or projects."
    if len(message) > MAX_INPUT_CHARS:
        return f"That message is a bit long. Could you keep it under {MAX_INPUT_CHARS} characters?"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *_clean_history(history or []), {"role": "user", "content": message}]

    for _ in range(MAX_TOOL_ROUNDS + 1):
        resp = client().chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=SCHEMAS,
            temperature=0.3,
            max_tokens=450,
        )
        choice = resp.choices[0]
        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            messages.append(choice.message)
            for call in choice.message.tool_calls:
                fn = REGISTRY.get(call.function.name)
                try:
                    args = json.loads(call.function.arguments or "{}")
                    result = fn(**args) if fn else {"error": "unknown tool"}
                except Exception:  # noqa: BLE001 - never surface internals to visitors
                    result = {"error": "tool failed"}
                messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
            continue

        text = choice.message.content or ""
        if _leaks_prompt(text):
            return FALLBACK
        return _scrub(text) or FALLBACK

    return "Sorry, that took longer than expected. Could you try asking again?"
