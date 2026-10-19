from __future__ import annotations

import difflib
import uuid
from dataclasses import dataclass

from ai_coding_agent.workspace import Workspace, WorkspaceError


@dataclass
class PendingFileChange:
    workspace: Workspace
    path: str
    content: str
    expected_content: str | None
    diff: str


class FileChangeManager:
    def __init__(self) -> None:
        self.pending: dict[str, PendingFileChange] = {}

    def propose(
        self,
        workspace: Workspace,
        path: str,
        content: str,
        expected_content: str | None = None,
    ) -> tuple[str, str]:
        previous = workspace.preview_write(path, content, expected_content)
        diff = "".join(
            difflib.unified_diff(
                (previous or "").splitlines(keepends=True),
                content.splitlines(keepends=True),
                fromfile=f"a/{path}" if previous is not None else "/dev/null",
                tofile=f"b/{path}",
            )
        )
        change_id = uuid.uuid4().hex
        self.pending[change_id] = PendingFileChange(
            workspace, path, content, expected_content, diff
        )
        return change_id, diff

    def approve(self, change_id: str) -> dict[str, object]:
        change = self.pending.pop(change_id, None)
        if change is None:
            raise WorkspaceError("File change approval is missing or already used.")
        path = change.workspace.write_file(
            change.path, change.content, change.expected_content
        )
        verified = change.workspace.read_file(path) == change.content
        if not verified:
            raise WorkspaceError("Written file did not match the approved content.")
        return {"written": path, "verified": True}
