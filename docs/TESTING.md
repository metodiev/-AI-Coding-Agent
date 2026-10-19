# Testing

## Run the core suite

Install development extras and run:

```powershell
pip install -e ".[dev]"
pytest
```

Tests cover settings/provider behavior, provider selection, workspace listing/search/
read/write/delete safeguards, traversal rejection, command allowlisting and approval,
agent tool proposals and iteration limits, and API routes. External inference is not
required for the core suite; the OpenAI missing-key path is tested without a credential.

## Optional live checks

- **Ollama:** start Ollama, pull a model, set the URL/model, run the app, then send a
  chat request using the Ollama provider.
- **OpenAI:** set a valid `OPENAI_API_KEY`, choose the configured model, and send a chat
  request. This consumes API quota and is not run as part of unit tests.

There are no automated live-provider integration tests yet. Provider selection,
missing-key behavior, and API-layer provider error propagation are covered with
offline tests; real hardware/model compatibility and account quota behavior remain
environment-dependent.

## Verification record

The final offline test run reported **18 passed, 1 skipped**. The skipped symlink test
could not create a symlink in this Windows environment. The test run also emitted a
Starlette TestClient/httpx deprecation warning. An Ollama model-list request succeeded,
but the attempted local inference request timed out with HTTP 504 at 90 seconds. Details
and exact commands are in [the build guide](BUILD_GUIDE.md).
