# Flexible AI Coding Agent

A local-first coding assistant that can use an Ollama model or the OpenAI API through
the same bounded agent loop. It provides a browser chat, workspace-scoped file tools,
project search, and approval-gated command execution.

## Features

- Provider and model selection at chat time (Ollama by default, OpenAI optional).
- Workspace file listing, reading, searching, and guarded writes.
- File writes create new files by default; replacing an existing file requires the
  exact `expected_content` read from the current version.
- Every agent-proposed file write is shown as a diff and requires approval before it
  changes the workspace.
- Deletion is available through the API and requires explicit confirmation.
- Commands are proposed first, restricted to an allowlist, and run only after approval.
- Bounded model/tool iterations, request/command timeouts, and visible tool results.
- Simple web chat UI. Conversation history is held in the browser for the current tab.

## Requirements

- Python 3.11 or newer.
- For local inference: [Ollama](https://ollama.com/) installed and a model downloaded.
- For OpenAI: an API key; local mode does not use or require it.

## Installation

From the repository root, in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
```

On macOS or Linux, activate with `source .venv/bin/activate` and copy the sample
configuration with `cp .env.example .env`.

## Configure a model

### Ollama (local)

Install Ollama, start it, then download a model, for example:

```powershell
ollama pull llama3.2
```

Set `AGENT_OLLAMA_BASE_URL` and `AGENT_OLLAMA_MODEL` in `.env` if the defaults
(`http://127.0.0.1:11434` and `llama3.2`) do not match. Use the refresh button in the
web interface to list models currently installed on the Ollama server. Availability
and response quality depend on your hardware and the model size.

### OpenAI (cloud)

Set `OPENAI_API_KEY` in `.env` and, optionally, `AGENT_OPENAI_MODEL` (default
`gpt-4o-mini`). The API key is read by the server only and is never returned by the
settings endpoint or sent to browser code. OpenAI usage may incur charges.

Provider choice can also be set as `AGENT_DEFAULT_PROVIDER=ollama` or `openai`.
Selecting OpenAI without a key reports an error; the app never silently switches
providers.

Terminal commands use an allowlist by default. Set `AGENT_COMMAND_POLICY=disabled` to
turn command execution off, or add executable names to `AGENT_EXTRA_COMMAND_NAMES`
(comma-separated) to extend the allowlist. All commands, including added ones, still
require explicit approval and run without a shell. Extending the allowlist increases
risk and is not a sandbox.

## Start and use

```powershell
uvicorn ai_coding_agent.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>, enter the absolute path of a project directory, choose a
provider/model, and describe the task. The chat displays each file tool result. If the
agent requests a terminal command, review the exact command and press its approval
button to run it. The command output and exit status are returned in the conversation.
File changes are also previewed as diffs and require approval before being written.

Example requests:

- "Inspect the project and explain how its tests are run."
- "Find where the settings are loaded and add a focused test for the default."
- "Create a small script under `scripts/` that lists the project files."

The first workspace tool call is subject to the selected directory boundary. The
agent only sees files it requests; it does not upload an index of the entire project.

## Validation

```powershell
pytest
```

The core suite runs without an OpenAI key or a running Ollama service. Optional live
provider checks are described in [docs/TESTING.md](docs/TESTING.md).

## Troubleshooting

- **Ollama connection error:** start Ollama and check `AGENT_OLLAMA_BASE_URL`.
- **Model unavailable:** run `ollama pull <model>` and refresh the model list.
- **OpenAI authentication error:** check the server-side `.env` key and restart Uvicorn.
- **OpenAI provider unavailable:** set `OPENAI_API_KEY`; local Ollama mode remains usable.
- **File path rejected:** select an existing directory and use paths relative to it for
  file operations. Traversal outside the selected workspace is rejected.
- **A command is rejected:** only the documented command allowlist is accepted; shell
  operators are not supported.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md),
[docs/SECURITY.md](docs/SECURITY.md), and [docs/MODEL_PROVIDERS.md](docs/MODEL_PROVIDERS.md)
for design and limitations.
