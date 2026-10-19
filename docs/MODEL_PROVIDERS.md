# Model providers

## Ollama

The local adapter posts non-streaming chat requests to
`{AGENT_OLLAMA_BASE_URL}/api/chat`. The model name is selected from `/api/tags` in the
UI or configured as `AGENT_OLLAMA_MODEL`. The default server URL is
`http://127.0.0.1:11434`.

Install Ollama from [ollama.com](https://ollama.com/), start its service, and pull a
model such as `ollama pull llama3.2`. Exact model names depend on the Ollama library.
Ollama availability, speed, and quality depend on the user's hardware and model.
Timeout and unreachable-server/model errors are surfaced by the API.

## OpenAI

The OpenAI adapter uses the official `openai` Python SDK and its chat completions API.
Set `OPENAI_API_KEY` in the server environment or an untracked `.env` file. The default
model is `gpt-4o-mini`; override it with `AGENT_OPENAI_MODEL` or select it in the UI.
The API handles missing credentials, authentication errors, rate limits, timeouts, and
other API failures without returning credentials to clients.

## Switching and adding providers

Choose **Ollama (local)** or **OpenAI (cloud)** and a model in the chat sidebar. Every
model/tool iteration in that request uses that same provider and model. There is no
silent paid-provider fallback. OpenAI models are not enumerated from the account; the
configured model is shown.

To add a provider, implement the `ModelProvider.complete(messages, model)` protocol,
register the provider in `create_app`, add explicit configuration and a selectable
name, then cover configuration and provider error handling with mocked unit tests.
Provider capabilities are limited to text completion in this MVP; provider-native
function calling and image input are not implemented.
