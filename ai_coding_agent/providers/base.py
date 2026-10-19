from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Message:
    role: str
    content: str


class ModelProvider(Protocol):
    async def complete(self, messages: list[Message], model: str) -> str:
        """Return one assistant response or raise ProviderError."""


class ProviderError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code
