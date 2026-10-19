from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ai_coding_agent.actions import FileChangeManager
from ai_coding_agent.agent import CodingAgent
from ai_coding_agent.config import Settings
from ai_coding_agent.providers.base import Message, ProviderError
from ai_coding_agent.providers.ollama import OllamaProvider
from ai_coding_agent.providers.openai_provider import OpenAIProvider
from ai_coding_agent.terminal import CommandError, CommandManager
from ai_coding_agent.workspace import Workspace, WorkspaceError

load_dotenv()
WEB_DIR = Path(__file__).parent / "web"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class ChatRequest(BaseModel):
    workspace: str = Field(min_length=1, max_length=2_000)
    provider: Literal["ollama", "openai"] | None = None
    model: str | None = Field(default=None, min_length=1, max_length=200)
    messages: list[ChatMessage] = Field(min_length=1, max_length=30)


class WorkspaceRequest(BaseModel):
    workspace: str = Field(min_length=1, max_length=2_000)


class WriteRequest(WorkspaceRequest):
    path: str = Field(min_length=1, max_length=2_000)
    content: str = Field(max_length=512_000)
    expected_content: str | None = Field(default=None, max_length=512_000)
    confirmed: bool = False


class DeleteRequest(WorkspaceRequest):
    path: str = Field(min_length=1, max_length=2_000)
    confirmed: bool = False


class SearchRequest(WorkspaceRequest):
    query: str = Field(min_length=1, max_length=500)


class CommandRequest(WorkspaceRequest):
    command: str = Field(min_length=1, max_length=1_000)


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    command_manager = CommandManager(
        timeout_seconds=60,
        policy=config.command_policy,
        extra_command_names=config.extra_command_names,
    )
    file_change_manager = FileChangeManager()
    agent = CodingAgent(
        command_manager, file_change_manager, max_iterations=config.max_iterations
    )
    app = FastAPI(
        title="Flexible AI Coding Agent",
        description="Local-first coding agent with Ollama and OpenAI providers.",
        version="0.1.0",
    )
    app.state.settings = config
    app.state.providers = {
        "ollama": OllamaProvider(config),
        "openai": OpenAIProvider(config),
    }
    app.state.command_manager = command_manager
    app.state.file_change_manager = file_change_manager
    app.state.agent = agent

    def selected_workspace(path: str) -> Workspace:
        try:
            return Workspace(path, extra_excludes=config.exclude_patterns)
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/settings")
    async def get_settings() -> dict[str, object]:
        return {
            "default_provider": config.default_provider,
            "ollama_base_url": config.ollama_base_url,
            "ollama_model": config.ollama_model,
            "openai_model": config.openai_model,
            "openai_configured": bool(config.openai_api_key),
            "max_iterations": config.max_iterations,
            "command_policy": config.command_policy,
        }

    @app.get("/api/models")
    async def get_models(provider: Literal["ollama", "openai"] = "ollama") -> dict[str, object]:
        if provider == "openai":
            if not config.openai_api_key:
                raise HTTPException(
                    status_code=400,
                    detail="Configure OPENAI_API_KEY before selecting OpenAI.",
                )
            return {"provider": provider, "models": [config.openai_model]}
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{config.ollama_base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
            if not isinstance(data, dict) or not isinstance(data.get("models"), list):
                raise HTTPException(status_code=502, detail="Ollama returned an invalid model list.")
            models = [
                item["name"]
                for item in data.get("models", [])
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            ]
            return {"provider": provider, "models": models}
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail="Ollama model request timed out.") from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=503,
                detail="Cannot retrieve models from Ollama; check that Ollama is running.",
            ) from exc
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=502, detail="Ollama returned invalid JSON.") from exc

    @app.post("/api/chat")
    async def chat(request: ChatRequest) -> dict[str, object]:
        provider_name = request.provider or config.default_provider
        model = request.model or (
            config.ollama_model if provider_name == "ollama" else config.openai_model
        )
        provider = app.state.providers[provider_name]
        try:
            result = await agent.run(
                provider,
                model,
                selected_workspace(request.workspace),
                [Message(role=item.role, content=item.content) for item in request.messages],
            )
            return {"provider": provider_name, "model": model, **result}
        except ProviderError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @app.get("/api/workspace/files")
    async def list_files(workspace: str, limit: int = 200) -> dict[str, object]:
        if not 1 <= limit <= 500:
            raise HTTPException(status_code=400, detail="limit must be from 1 to 500.")
        try:
            return {"files": selected_workspace(workspace).list_files(limit)}
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/workspace/file")
    async def read_file(workspace: str, path: str) -> dict[str, str]:
        try:
            return {"path": path, "content": selected_workspace(workspace).read_file(path)}
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/workspace/search")
    async def search(request: SearchRequest) -> dict[str, object]:
        try:
            return {"matches": selected_workspace(request.workspace).search(request.query)}
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/workspace/file")
    async def write_file(request: WriteRequest) -> dict[str, str]:
        if not request.confirmed:
            raise HTTPException(
                status_code=400, detail="Explicit confirmation is required to write a file."
            )
        try:
            path = selected_workspace(request.workspace).write_file(
                request.path, request.content, request.expected_content
            )
            return {"written": path}
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/files/{change_id}/approve")
    async def approve_file_change(change_id: str) -> dict[str, object]:
        try:
            return file_change_manager.approve(change_id)
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/workspace/file")
    async def delete_file(request: DeleteRequest) -> dict[str, str]:
        try:
            path = selected_workspace(request.workspace).delete_file(
                request.path, request.confirmed
            )
            return {"deleted": path}
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/commands/propose")
    async def propose_command(request: CommandRequest) -> dict[str, object]:
        workspace = selected_workspace(request.workspace)
        try:
            command_id, command = command_manager.propose(request.command, workspace.root)
            return {
                "approval_id": command_id,
                "command": command,
                "approval_required": True,
            }
        except CommandError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/commands/{command_id}/approve")
    async def approve_command(command_id: str) -> dict[str, object]:
        try:
            return command_manager.approve(command_id)
        except CommandError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
    return app


app = create_app()
