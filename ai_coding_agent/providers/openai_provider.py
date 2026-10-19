from __future__ import annotations

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from ai_coding_agent.config import Settings
from ai_coding_agent.providers.base import Message, ProviderError


class OpenAIProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def complete(self, messages: list[Message], model: str) -> str:
        if not self.settings.openai_api_key:
            raise ProviderError(
                "OpenAI is selected but OPENAI_API_KEY is not configured.", 400
            )
        client = AsyncOpenAI(
            api_key=self.settings.openai_api_key,
            timeout=self.settings.request_timeout_seconds,
            max_retries=0,
        )
        try:
            result = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": message.role, "content": message.content}
                    for message in messages
                ],
            )
            content = result.choices[0].message.content
            if content is None:
                raise ProviderError("OpenAI returned an empty response.")
            return content
        except APITimeoutError as exc:
            raise ProviderError("OpenAI request timed out.", 504) from exc
        except APIConnectionError as exc:
            raise ProviderError("Could not connect to the OpenAI API.", 503) from exc
        except APIStatusError as exc:
            if exc.status_code == 401:
                raise ProviderError("OpenAI authentication failed; check the API key.", 401) from exc
            if exc.status_code == 429:
                raise ProviderError("OpenAI rate limit or quota exceeded.", 429) from exc
            raise ProviderError(
                f"OpenAI API request failed (HTTP {exc.status_code}).", 502
            ) from exc
        finally:
            await client.close()
