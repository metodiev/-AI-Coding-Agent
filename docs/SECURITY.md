# Security

## Workspace and file permissions

The API requires an existing selected directory. File paths are resolved and checked
to remain under that directory; symlinks are rejected. `.git`, virtual environments,
dependency/build output directories, configured `.gitignore` paths, and files larger
than 512 KB are excluded from listing/reading.
Common credential files (`.env*`, `*.pem`, `*.key`, and names containing `credentials`
or `secret`) are excluded by default. Additional comma-separated patterns can be set in
`AGENT_EXCLUDE_PATTERNS`.
Agent writes are previewed as unified diffs and require explicit approval before they
are applied. New files can be created directly; replacing an existing text file
requires its exact previously read content as `expected_content`. Deletes require
`confirmed: true`. These safeguards reduce accidental changes but do not make the
workspace a security sandbox.

## Terminal policy

Commands must match the default allowlist (`pytest`, `python -m pytest`, `git status`,
`git diff`, `ruff check`, `ruff format --check`) and are always proposed for explicit
user approval. Set `AGENT_COMMAND_POLICY=disabled` for a stricter policy, or add
executable names to `AGENT_EXTRA_COMMAND_NAMES` to extend the allowlist. Added
executables still require approval and use `shell=False`; configure them only when
needed, as they may run arbitrary code.
Execution uses an argument vector, `shell=False`, the selected workspace as the working
directory, and a 60-second timeout. No shell operators are accepted. This is not an OS
sandbox: approved test tools or repository hooks/plugins can execute code with the
server user's permissions. Do not approve commands you do not understand.

## Credentials and privacy

OpenAI credentials are read from the server process environment (or `.env`, which is
ignored by Git). They are not exposed by API responses or browser JavaScript. Never
put real credentials in `.env.example`. Local mode sends prompts only to the configured
Ollama endpoint. OpenAI mode sends conversation messages to OpenAI. The agent does not
persist server-side chat history; the current browser tab retains its conversation.

## Network exposure and limitations

The documented startup command binds to `127.0.0.1`. The app has no user authentication,
CSRF protection, multi-user isolation, audit log, or hardened sandbox. Do not bind it
to a public or shared network. Workspace paths are provided by the client and this app
is intended for a trusted local user. Review all generated changes and command output.
The OS user running the app retains its ordinary filesystem/network permissions.
