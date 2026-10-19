# Roadmap

## Completed in the initial MVP

- FastAPI web app and browser chat.
- Ollama and OpenAI adapters behind one provider protocol.
- Provider/model selection and server-only OpenAI key handling.
- Workspace listing, reading, searching, diff-previewed/approved writes, and confirmed
  deletion API.
- Bounded JSON-tool agent loop and approval-gated allowlisted commands.
- Focused offline automated tests and security/provider documentation.

## Current limitations

- JSON tool-call prompting is less reliable than native provider tool calling.
- No persistent task history, multi-user auth, or OS sandbox. The initial file-change
  approval previews one proposed file at a time; no Git status/diff dashboard exists.
- The UI permits one workspace path at a time and is designed for local use.
- Live Ollama/OpenAI integration depends on local hardware, network access, model
  availability, credentials, and external service quotas.

## Next improvements

- Add a Git status/diff dashboard and richer review of multi-file change sets.
- Add durable task history with explicit retention controls.
- Add richer ignore parsing and optional context budgeting for large repositories.
- Add native function/tool calling where supported while keeping provider parity.
- Introduce process-level sandboxing before supporting untrusted/public deployments.
