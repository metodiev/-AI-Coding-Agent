from __future__ import annotations

import json

import httpx

from ai_coding_agent.config import Settings
from ai_coding_agent.providers.base import Message, ProviderError


class OllamaProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def complete(self, messages: list[Message], model: str) -> str:
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.request_timeout_seconds
            ) as client:
                response = await client.post(
                    f"{self.settings.ollama_base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": [
                            {"role": message.role, "content": message.content}
                            for message in messages
                        ],
                        "stream": False,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or not isinstance(
                    payload.get("message"), dict
                ):
                    raise ProviderError("Ollama returned an invalid chat response.")
                content = payload["message"].get("content")
                if not isinstance(content, str):
                    raise ProviderError("Ollama returned an invalid chat response.")
                return content
        except httpx.TimeoutException as exc:
            raise ProviderError("Ollama request timed out.", 504) from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            message = "Ollama rejected the request."
            if status == 404:
                message = f"Ollama model '{model}' is unavailable. Pull it in Ollama first."
            raise ProviderError(message, 503 if status == 404 else 502) from exc
        except httpx.RequestError as exc:
            raise ProviderError(
                "Cannot reach Ollama. Check that Ollama is running and its URL is correct.",
                503,
            ) from exc
        except json.JSONDecodeError as exc:
            raise ProviderError("Ollama returned invalid JSON.") from exc
