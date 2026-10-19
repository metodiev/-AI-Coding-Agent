from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from ai_coding_agent.actions import FileChangeManager
from ai_coding_agent.agent import CodingAgent
from ai_coding_agent.config import Settings
from ai_coding_agent.main import create_app
from ai_coding_agent.providers.base import Message, ProviderError
from ai_coding_agent.providers.openai_provider import OpenAIProvider
from ai_coding_agent.terminal import CommandError, CommandManager
from ai_coding_agent.workspace import Workspace, WorkspaceError


class SequenceProvider:
    def __init__(self, *responses: str):
        self.responses = list(responses)
        self.models: list[str] = []

    async def complete(self, messages: list[Message], model: str) -> str:
        self.models.append(model)
        return self.responses.pop(0)


def make_workspace(tmp_path: Path) -> Workspace:
    return Workspace(tmp_path)


def test_workspace_lists_respects_gitignore_and_excludes(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("private.txt\nignored/\n", encoding="utf-8")
    (tmp_path / "visible.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "private.txt").write_text("secret", encoding="utf-8")
    (tmp_path / "ignored").mkdir()
    (tmp_path / "ignored" / "data.txt").write_text("ignored", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("repo", encoding="utf-8")
    (tmp_path / ".env").write_text("API_KEY=not-visible", encoding="utf-8")

    assert make_workspace(tmp_path).list_files() == [".gitignore", "visible.py"]


def test_workspace_applies_extra_exclusion_patterns(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("not indexed", encoding="utf-8")
    (tmp_path / "keep.txt").write_text("indexed", encoding="utf-8")
    assert Workspace(tmp_path, extra_excludes=("notes.*",)).list_files() == ["keep.txt"]


def test_workspace_rejects_traversal_and_absolute_paths(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    for path in ("../outside.txt", str(tmp_path / "outside.txt")):
        with pytest.raises(WorkspaceError):
            workspace.read_file(path)


def test_workspace_rejects_symlinks(tmp_path: Path) -> None:
    target = tmp_path / "real.txt"
    target.write_text("inside", encoding="utf-8")
    alias = tmp_path / "alias.txt"
    try:
        alias.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is not permitted in this environment.")
    with pytest.raises(WorkspaceError, match="Symbolic links"):
        make_workspace(tmp_path).read_file("alias.txt")


def test_workspace_write_read_and_confirmed_delete(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    assert workspace.write_file("src/new.py", "print('ok')") == "src/new.py"
    assert workspace.read_file("src/new.py") == "print('ok')"
    with pytest.raises(WorkspaceError, match="already exists"):
        workspace.write_file("src/new.py", "overwrite")
    with pytest.raises(WorkspaceError, match="changed since it was read"):
        workspace.write_file("src/new.py", "overwrite", "stale")
    assert workspace.write_file("src/new.py", "updated", "print('ok')") == "src/new.py"
    assert workspace.read_file("src/new.py") == "updated"
    with pytest.raises(WorkspaceError, match="confirmation"):
        workspace.delete_file("src/new.py", confirmed=False)
    assert workspace.delete_file("src/new.py", confirmed=True) == "src/new.py"


def test_workspace_search_is_case_insensitive(tmp_path: Path) -> None:
    (tmp_path / "app.txt").write_text("The Quick Brown Fox", encoding="utf-8")
    result = make_workspace(tmp_path).search("quick")
    assert result == [{"path": "app.txt", "line": 1, "text": "The Quick Brown Fox"}]


def test_command_requires_approval_and_shell_operators_are_rejected(tmp_path: Path) -> None:
    manager = CommandManager()
    with pytest.raises(CommandError, match="not on the allowlist"):
        manager.propose("python -c print(1)", tmp_path)
    with pytest.raises(CommandError, match="Shell operators"):
        manager.propose("pytest; whoami", tmp_path)
    command_id, _ = manager.propose("pytest --version", tmp_path)
    assert command_id in manager.pending


def test_command_approval_runs_only_once(tmp_path: Path) -> None:
    manager = CommandManager()
    command_id, _ = manager.propose("pytest --version", tmp_path)
    result = manager.approve(command_id)
    assert result["succeeded"] is True
    assert "pytest" in str(result["stdout"]).lower()
    with pytest.raises(CommandError, match="missing"):
        manager.approve(command_id)


def test_command_policy_can_disable_or_extend_allowlist(tmp_path: Path) -> None:
    disabled = CommandManager(policy="disabled")
    with pytest.raises(CommandError, match="disabled"):
        disabled.propose("pytest --version", tmp_path)
    extended = CommandManager(extra_command_names=("node",))
    command_id, _ = extended.propose("node --version", tmp_path)
    assert command_id in extended.pending


@pytest.mark.asyncio
async def test_agent_executes_workspace_tool_then_uses_same_provider_and_model(
    tmp_path: Path,
) -> None:
    tool_call = json.dumps(
        {"tool": "write_file", "arguments": {"path": "new.txt", "content": "done"}}
    )
    provider = SequenceProvider(tool_call, "Created new.txt and verified the change.")
    file_changes = FileChangeManager()
    agent = CodingAgent(CommandManager(), file_changes, max_iterations=3)
    result = await agent.run(
        provider,
        "local-test-model",
        make_workspace(tmp_path),
        [Message(role="user", content="Create new.txt.")],
    )
    assert not (tmp_path / "new.txt").exists()
    proposal = result["tool_events"][0]["result"]
    assert proposal["approval_required"] is True
    assert proposal["approval_type"] == "file"
    assert "+done" in proposal["diff"]
    assert file_changes.approve(proposal["approval_id"]) == {
        "written": "new.txt",
        "verified": True,
    }
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "done"
    assert "awaiting your approval" in result["response"]
    assert provider.models == ["local-test-model", "local-test-model"]


@pytest.mark.asyncio
async def test_agent_iteration_limit_is_reported(tmp_path: Path) -> None:
    provider = SequenceProvider(
        '{"tool":"list_files","arguments":{}}',
        '{"tool":"list_files","arguments":{}}',
    )
    result = await CodingAgent(
        CommandManager(), FileChangeManager(), max_iterations=2
    ).run(
        provider,
        "test",
        make_workspace(tmp_path),
        [Message(role="user", content="List files.")],
    )
    assert result["iteration_limit_reached"] is True
    assert len(result["tool_events"]) == 2


@pytest.mark.asyncio
async def test_openai_requires_key_before_network_call() -> None:
    settings = Settings(openai_api_key=None)
    with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
        await OpenAIProvider(settings).complete(
            [Message(role="user", content="hello")], "gpt-test"
        )


def test_settings_load_provider_and_exclusions_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_DEFAULT_PROVIDER", "openai")
    monkeypatch.setenv("AGENT_EXCLUDE_PATTERNS", "cache/, *.generated")
    settings = Settings.from_env()
    assert settings.default_provider == "openai"
    assert settings.exclude_patterns == ("cache/", "*.generated")


def test_api_provider_settings_workspace_and_approval(tmp_path: Path) -> None:
    app = create_app(Settings(openai_api_key=None))
    fake = AsyncMock()
    fake.complete.return_value = "The project is ready."
    app.state.providers["ollama"] = fake
    client = TestClient(app)

    settings_response = client.get("/api/settings")
    assert settings_response.status_code == 200
    assert settings_response.json()["openai_configured"] is False

    (tmp_path / "hello.py").write_text("print('hello')", encoding="utf-8")
    files = client.get(
        "/api/workspace/files",
        params={"workspace": str(tmp_path)},
    )
    assert files.json()["files"] == ["hello.py"]

    chat = client.post(
        "/api/chat",
        json={
            "workspace": str(tmp_path),
            "provider": "ollama",
            "model": "chosen-model",
            "messages": [{"role": "user", "content": "Explain the project."}],
        },
    )
    assert chat.status_code == 200
    assert chat.json()["model"] == "chosen-model"
    assert fake.complete.await_args.args[1] == "chosen-model"

    proposal = client.post(
        "/api/commands/propose",
        json={"workspace": str(tmp_path), "command": "pytest --version"},
    )
    assert proposal.status_code == 200
    assert proposal.json()["approval_required"] is True
    result = client.post(f"/api/commands/{proposal.json()['approval_id']}/approve")
    assert result.status_code == 200
    assert result.json()["succeeded"] is True


def test_api_reports_openai_unavailable_without_secret(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(openai_api_key=None)))
    response = client.get("/api/models?provider=openai")
    assert response.status_code == 400
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_api_surfaces_provider_errors(tmp_path: Path) -> None:
    app = create_app(Settings())
    fake = AsyncMock()
    fake.complete.side_effect = ProviderError("Ollama is offline.", 503)
    app.state.providers["ollama"] = fake
    response = TestClient(app).post(
        "/api/chat",
        json={
            "workspace": str(tmp_path),
            "provider": "ollama",
            "messages": [{"role": "user", "content": "Help."}],
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Ollama is offline."


def test_api_requires_explicit_delete_confirmation(tmp_path: Path) -> None:
    file = tmp_path / "keep.txt"
    file.write_text("keep", encoding="utf-8")
    client = TestClient(create_app(Settings()))
    response = client.request(
        "DELETE",
        "/api/workspace/file",
        json={"workspace": str(tmp_path), "path": "keep.txt", "confirmed": False},
    )
    assert response.status_code == 400
    assert file.exists()


def test_api_file_write_requires_approval_and_returns_verified_result(
    tmp_path: Path,
) -> None:
    app = create_app(Settings())
    fake = AsyncMock()
    fake.complete.side_effect = [
        json.dumps(
            {"tool": "write_file", "arguments": {"path": "new.txt", "content": "approved"}}
        ),
        "A proposed file change is waiting for your approval.",
    ]
    app.state.providers["ollama"] = fake
    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={
            "workspace": str(tmp_path),
            "provider": "ollama",
            "messages": [{"role": "user", "content": "Create new.txt."}],
        },
    )
    assert response.status_code == 200
    proposal = response.json()["tool_events"][0]["result"]
    assert not (tmp_path / "new.txt").exists()
    approval = client.post(f"/api/files/{proposal['approval_id']}/approve")
    assert approval.status_code == 200
    assert approval.json() == {"written": "new.txt", "verified": True}
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "approved"


def test_api_direct_write_requires_confirmation(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings()))
    response = client.put(
        "/api/workspace/file",
        json={"workspace": str(tmp_path), "path": "x.txt", "content": "text"},
    )
    assert response.status_code == 400
    assert not (tmp_path / "x.txt").exists()
