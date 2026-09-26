"""Thin, provider-agnostic LLM client used by the CI/CD GenAI steps.

Supported providers (auto-detected, in order):
  1. OpenAI            -> requires ``OPENAI_API_KEY``
  2. GitHub Models     -> requires ``GITHUB_TOKEN`` with the ``models: read`` permission

The client is intentionally fail-soft: if no provider is configured, or the API
call fails, it returns ``None`` so the pipeline degrades to a deterministic
fallback instead of breaking the build. AI is an assistant here, never a gate.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass

import requests

TIMEOUT_SECONDS = 90
MAX_PROMPT_CHARS = 24_000

# Defence in depth: strip anything that looks like a credential before it can
# leave the runner, even though workflows only feed diffs and logs to the model.
_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(dapi[0-9a-f]{32,})"),
    re.compile(r"(?i)\b(gh[pousr]_[A-Za-z0-9]{20,})"),
    re.compile(r"(?i)\b(sk-[A-Za-z0-9\-_]{20,})"),
    re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*\S+"),
)


def redact(text: str) -> str:
    """Mask credential-shaped substrings."""
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("***REDACTED***", text)
    return text


@dataclass(frozen=True)
class Provider:
    name: str
    url: str
    api_key: str
    model: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}


def resolve_provider() -> Provider | None:
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key:
        return Provider(
            name="openai",
            url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1") + "/chat/completions",
            api_key=openai_key,
            model=os.environ.get("AI_MODEL", "gpt-4o-mini"),
        )

    gh_token = os.environ.get("GITHUB_TOKEN", "").strip()
    if gh_token:
        return Provider(
            name="github-models",
            url="https://models.github.ai/inference/chat/completions",
            api_key=gh_token,
            model=os.environ.get("AI_MODEL", "openai/gpt-4o-mini"),
        )
    return None


def complete(system_prompt: str, user_prompt: str, max_tokens: int = 900) -> str | None:
    """Return the model's answer, or ``None`` when AI is unavailable."""
    provider = resolve_provider()
    if provider is None:
        print("[ai] No AI provider configured (OPENAI_API_KEY / GITHUB_TOKEN). Skipping.", file=sys.stderr)
        return None

    payload = {
        "model": provider.model,
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": redact(user_prompt)[:MAX_PROMPT_CHARS]},
        ],
    }

    try:
        response = requests.post(
            provider.url, headers=provider.headers, json=payload, timeout=TIMEOUT_SECONDS
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    except (requests.RequestException, KeyError, ValueError) as exc:
        print(f"[ai] Provider '{provider.name}' call failed: {exc}", file=sys.stderr)
        return None

    print(f"[ai] Generated {len(content)} chars via {provider.name}/{provider.model}", file=sys.stderr)
    return content.strip()
