from __future__ import annotations

import shlex
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

ALLOWED_PREFIXES = (
    ("pytest",),
    ("python", "-m", "pytest"),
    ("git", "status"),
    ("git", "diff"),
    ("ruff", "check"),
    ("ruff", "format", "--check"),
)
FORBIDDEN_SHELL_TOKENS = {";", "&&", "||", "|", ">", ">>", "<", "$(", "`"}


class CommandError(ValueError):
    pass


@dataclass
class PendingCommand:
    command: str
    workspace: Path


class CommandManager:
    def __init__(
        self,
        timeout_seconds: int = 60,
        policy: str = "allowlist",
        extra_command_names: tuple[str, ...] = (),
    ):
        self.timeout_seconds = timeout_seconds
        if policy not in {"disabled", "allowlist"}:
            raise ValueError("Command policy must be 'disabled' or 'allowlist'.")
        self.policy = policy
        self.extra_command_names = frozenset(extra_command_names)
        self.pending: dict[str, PendingCommand] = {}

    @staticmethod
    def _split(command: str) -> list[str]:
        try:
            args = shlex.split(command, posix=False)
        except ValueError as exc:
            raise CommandError("Command could not be parsed.") from exc
        return [
            arg[1:-1]
            if len(arg) >= 2 and arg[0] == arg[-1] and arg[0] in {"'", '"'}
            else arg
            for arg in args
        ]

    def propose(self, command: str, workspace: Path) -> tuple[str, str]:
        if self.policy == "disabled":
            raise CommandError("Terminal command execution is disabled by configuration.")
        args = self._split(command)
        if not args or any(token in command for token in FORBIDDEN_SHELL_TOKENS):
            raise CommandError("Shell operators and empty commands are not allowed.")
        allowed = any(tuple(args[: len(prefix)]) == prefix for prefix in ALLOWED_PREFIXES)
        allowed = allowed or args[0] in self.extra_command_names
        if not allowed:
            raise CommandError(
                "Command is not on the allowlist. Allowed: pytest, git status/diff, "
                "ruff check, ruff format --check, and explicitly configured commands."
            )
        if args[0] == "git" and any(arg.startswith("-C") for arg in args):
            raise CommandError("Git cannot be directed outside the selected workspace.")
        command_id = uuid.uuid4().hex
        self.pending[command_id] = PendingCommand(command, workspace)
        return command_id, command

    def approve(self, command_id: str) -> dict[str, object]:
        pending = self.pending.pop(command_id, None)
        if pending is None:
            raise CommandError("Command approval is missing, expired, or already used.")
        try:
            args = self._split(pending.command)
            result = subprocess.run(
                args,
                cwd=pending.workspace,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise CommandError(
                f"Command exceeded the {self.timeout_seconds}-second timeout."
            ) from exc
        except OSError as exc:
            raise CommandError(f"Could not start approved command: {exc}") from exc
        return {
            "command": pending.command,
            "return_code": result.returncode,
            "stdout": result.stdout[-20_000:],
            "stderr": result.stderr[-20_000:],
            "succeeded": result.returncode == 0,
        }
