# Build guide

This guide records the initial implementation milestones and observed validation for
this repository. The repository began with only a short README and the MIT license.

## Milestone 1: project foundation

- Added a Python package, `pyproject.toml`, environment example, and Git ignores.
- Centralized environment configuration in `ai_coding_agent/config.py`.
- Chose FastAPI, Pydantic, httpx, the official OpenAI SDK, and pytest to keep the
  implementation small and typed.
- Files: `pyproject.toml`, `.env.example`, `.gitignore`, and `ai_coding_agent/config.py`.
- Design reason: environment-based configuration keeps local-only use independent of
  cloud credentials, while optional development dependencies keep runtime setup lean.

## Milestone 2: providers and agent loop

- Added a shared provider protocol with Ollama and OpenAI adapters.
- Added an agent loop that sends messages through the selected adapter, dispatches only
  recognized JSON tools, returns tool outcomes to the model, and stops at a configured
  iteration cap.
- Provider/model choice is kept fixed throughout each request. Provider-specific
  failures become explicit HTTP errors.
- Files: `ai_coding_agent/providers/`, `ai_coding_agent/agent.py`, and API setup in
  `ai_coding_agent/main.py`.
- Design reason: a single text-completion protocol avoids duplicating orchestration for
  local and cloud model providers; JSON tool requests avoid vendor-specific APIs.

## Milestone 3: workspace tools and command control

- Added file listing, read, search, and write operations rooted at the selected folder.
- Added ignored/secret patterns, size limits, traversal and symlink checks. Existing
  files require an exact expected-content match to be overwritten; deleting requires
  explicit confirmation.
- File changes are returned as unified diffs and must be approved before they are
  committed; the server reads back approved writes to verify the saved contents.
- Added a command proposal/approval API. Commands are allowlisted, run with
  `shell=False`, and constrained by timeout and working directory.
- Files: `ai_coding_agent/workspace.py`, `ai_coding_agent/actions.py`,
  `ai_coding_agent/terminal.py`, and related API routes.
- Design reason: an explicit diff/approval step and constrained subprocess interface
  are safer than direct model writes or unrestricted shell access.

## Milestone 4: interface and documentation

- Added the static web chat with provider/model selectors and visible tool results.
- Added README, architecture, build, provider, security, testing, decision, roadmap,
  and changelog documentation. The docs distinguish tested offline behavior from
  environment-dependent live model use.
- Files: `ai_coding_agent/web/`, `README.md`, `docs/`, and `CHANGELOG.md`.
- Design reason: the browser app is static and local-first, with no frontend build
  toolchain or server-side conversation persistence.

## Validation

Commands run in the development environment:

```text
python -m pip install -e ".[dev]"  -> succeeded
python -m pytest -q -rs             -> 18 passed, 1 skipped, 1 warning
python -m compileall -q ai_coding_agent tests -> succeeded
git diff --check                    -> succeeded
```

The skipped test covers symlink rejection; this Windows environment did not permit
creating a test symlink. The warning comes from the installed Starlette TestClient
noting its httpx integration deprecation. The web app and model-list UI were served
successfully in a browser. A real Ollama chat request using `qwen2.5-coder:1.5b-base`
returned HTTP 504 at the configured 90-second request timeout, so inference is not
verified in this environment. No OpenAI API request was attempted.
