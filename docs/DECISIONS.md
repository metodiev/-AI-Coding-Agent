# Architecture decisions

## FastAPI and a small static client

Use FastAPI for typed JSON endpoints and serve a framework-free browser UI. This keeps
installation and runtime surface small while meeting the local web-chat requirement.
A richer frontend framework is deferred until the core workflows are stable.

## Provider protocol, not provider-specific orchestration

The agent depends on one `complete(messages, model)` protocol. Provider selection is
per request, so local and cloud runs share the same instructions, tools, and iteration
limit. OpenAI uses its maintained official SDK; Ollama uses its documented HTTP API.

## JSON tool dispatch

The MVP asks models to emit one small JSON object for a tool call rather than relying
on provider-specific function calling. This preserves a uniform provider interface.
Models that fail to produce the exact shape return their text as an ordinary response;
no command or file operation is inferred from unstructured prose.

## Explicit command approval and narrow allowlist

An agent can propose but cannot run a terminal command. The user must approve a
one-use proposal, and the runner uses `shell=False`, a configurable allowlist, a
timeout, and workspace working directory. A general shell was rejected because it is
unnecessarily powerful for a local MVP. This still is not a sandbox.

## Conservative file writes and ephemeral chat

New files are presented as unified diffs and require approval before being written.
Replacing an existing file also requires an exact expected-content match, reducing
the chance of overwriting concurrent/unread work. Delete requires confirmation. Chat
history remains in the current tab rather than being persisted server-side; persistent
task history needs an explicit retention and privacy design.
