from __future__ import annotations

import os
from dataclasses import dataclass


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True)
class Settings:
    default_provider: str = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    max_iterations: int = 5
    request_timeout_seconds: int = 90
    exclude_patterns: tuple[str, ...] = ()
    command_policy: str = "allowlist"
    extra_command_names: tuple[str, ...] = ()

    @classmethod
    def from_env(cls) -> Settings:
        provider = os.getenv("AGENT_DEFAULT_PROVIDER", "ollama").strip().lower()
        if provider not in {"ollama", "openai"}:
            raise ValueError("AGENT_DEFAULT_PROVIDER must be 'ollama' or 'openai'")
        command_policy = os.getenv("AGENT_COMMAND_POLICY", "allowlist").strip().lower()
        if command_policy not in {"disabled", "allowlist"}:
            raise ValueError("AGENT_COMMAND_POLICY must be 'disabled' or 'allowlist'")
        return cls(
            default_provider=provider,
            ollama_base_url=os.getenv(
                "AGENT_OLLAMA_BASE_URL", "http://127.0.0.1:11434"
            ).rstrip("/"),
            ollama_model=os.getenv("AGENT_OLLAMA_MODEL", "llama3.2"),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            openai_model=os.getenv("AGENT_OPENAI_MODEL", "gpt-4o-mini"),
            max_iterations=_positive_int("AGENT_MAX_ITERATIONS", 5),
            request_timeout_seconds=_positive_int(
                "AGENT_REQUEST_TIMEOUT_SECONDS", 90
            ),
            exclude_patterns=tuple(
                pattern.strip()
                for pattern in os.getenv("AGENT_EXCLUDE_PATTERNS", "").split(",")
                if pattern.strip()
            ),
            command_policy=command_policy,
            extra_command_names=tuple(
                name.strip()
                for name in os.getenv("AGENT_EXTRA_COMMAND_NAMES", "").split(",")
                if name.strip()
            ),
        )
