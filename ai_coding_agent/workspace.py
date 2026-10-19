from __future__ import annotations

import fnmatch
import os
from pathlib import Path

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
}
MAX_FILE_BYTES = 512_000
SENSITIVE_PATTERNS = (".env", ".env.*", "*.pem", "*.key", "*credentials*", "*secret*")


class WorkspaceError(ValueError):
    pass


class Workspace:
    def __init__(self, root: str | Path, extra_excludes: tuple[str, ...] = ()):
        path = Path(root).expanduser().resolve()
        if not path.exists() or not path.is_dir():
            raise WorkspaceError("Workspace must be an existing directory.")
        self.root = path
        self.extra_excludes = extra_excludes
        self.ignore_patterns = self._read_gitignore()

    def _read_gitignore(self) -> list[str]:
        ignore_file = self.root / ".gitignore"
        if not ignore_file.is_file():
            return []
        try:
            return [
                line.strip()
                for line in ignore_file.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
        except (OSError, UnicodeError) as exc:
            raise WorkspaceError(f"Could not read workspace .gitignore: {exc}") from exc

    def resolve(self, relative_path: str) -> Path:
        if not relative_path or Path(relative_path).is_absolute():
            raise WorkspaceError("A non-empty relative workspace path is required.")
        lexical_path = Path(os.path.abspath(self.root / relative_path))
        try:
            lexical_path.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceError("Path is outside the selected workspace.") from exc
        parent = lexical_path
        while parent != self.root:
            if parent.is_symlink():
                raise WorkspaceError("Symbolic links are not accessible in the workspace.")
            parent = parent.parent
        candidate = lexical_path.resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceError("Path is outside the selected workspace.") from exc
        return candidate

    def _ignored(self, relative: str, is_dir: bool = False) -> bool:
        parts = Path(relative).parts
        if any(part in EXCLUDED_DIRS for part in parts):
            return True
        normalized = relative.replace(os.sep, "/")
        if any(fnmatch.fnmatch(part, pattern) for part in parts for pattern in SENSITIVE_PATTERNS):
            return True
        ignored = False
        for pattern in self.ignore_patterns + list(self.extra_excludes):
            negated = pattern.startswith("!")
            pattern = pattern[1:] if negated else pattern
            directory_pattern = pattern.endswith("/")
            pattern = pattern.lstrip("/").rstrip("/")
            if "/" in pattern:
                match = fnmatch.fnmatch(normalized, pattern)
                if directory_pattern:
                    prefixes = [
                        Path(*parts[:index]).as_posix()
                        for index in range(1, len(parts) + 1)
                    ]
                    match = match or any(fnmatch.fnmatch(prefix, pattern) for prefix in prefixes)
            else:
                match = any(fnmatch.fnmatch(part, pattern) for part in parts)
            if match:
                ignored = not negated
        return ignored

    def list_files(self, limit: int = 200) -> list[str]:
        files: list[str] = []
        for current, dirs, names in os.walk(self.root, followlinks=False):
            current_path = Path(current)
            relative_dir = current_path.relative_to(self.root).as_posix()
            dirs[:] = [
                name
                for name in dirs
                if not (current_path / name).is_symlink()
                and not self._ignored(
                    (Path(relative_dir) / name).as_posix().lstrip("./"), True
                )
            ]
            for name in names:
                item = current_path / name
                relative = item.relative_to(self.root).as_posix()
                if item.is_symlink() or self._ignored(relative):
                    continue
                if item.is_file() and item.stat().st_size <= MAX_FILE_BYTES:
                    files.append(relative)
                    if len(files) >= limit:
                        return sorted(files)
        return sorted(files)

    def read_file(self, relative_path: str) -> str:
        path = self.resolve(relative_path)
        if not path.is_file():
            raise WorkspaceError("File does not exist in the selected workspace.")
        if path.is_symlink() or self._ignored(path.relative_to(self.root).as_posix()):
            raise WorkspaceError("This file is excluded from workspace access.")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise WorkspaceError(f"File exceeds the {MAX_FILE_BYTES}-byte read limit.")
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeError as exc:
            raise WorkspaceError("File is not valid UTF-8 text.") from exc

    def write_file(
        self,
        relative_path: str,
        content: str,
        expected_content: str | None = None,
    ) -> str:
        path = self.resolve(relative_path)
        relative = path.relative_to(self.root).as_posix()
        if self._ignored(relative):
            raise WorkspaceError("Writing to excluded files is not permitted.")
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise WorkspaceError(f"File exceeds the {MAX_FILE_BYTES}-byte write limit.")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if not path.is_file():
                raise WorkspaceError("Only regular files can be overwritten.")
            if path.stat().st_size > MAX_FILE_BYTES:
                raise WorkspaceError(f"File exceeds the {MAX_FILE_BYTES}-byte write limit.")
            if expected_content is None:
                raise WorkspaceError(
                    "File already exists; read it and supply expected_content to replace it."
                )
            try:
                actual_content = path.read_text(encoding="utf-8")
            except UnicodeError as exc:
                raise WorkspaceError("Existing file is not valid UTF-8 text.") from exc
            if actual_content != expected_content:
                raise WorkspaceError(
                    "File changed since it was read; inspect it again before replacing."
                )
            path.write_text(content, encoding="utf-8")
        else:
            try:
                with path.open("x", encoding="utf-8", newline="") as output:
                    output.write(content)
            except FileExistsError as exc:
                raise WorkspaceError(
                    "File was created concurrently; inspect it before replacing."
                ) from exc
        return relative

    def preview_write(
        self,
        relative_path: str,
        content: str,
        expected_content: str | None = None,
    ) -> str | None:
        path = self.resolve(relative_path)
        relative = path.relative_to(self.root).as_posix()
        if self._ignored(relative):
            raise WorkspaceError("Writing to excluded files is not permitted.")
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise WorkspaceError(f"File exceeds the {MAX_FILE_BYTES}-byte write limit.")
        if not path.exists():
            if expected_content is not None:
                raise WorkspaceError("File changed since it was read; inspect it again.")
            return None
        if not path.is_file():
            raise WorkspaceError("Only regular files can be overwritten.")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise WorkspaceError(f"File exceeds the {MAX_FILE_BYTES}-byte write limit.")
        try:
            actual_content = path.read_text(encoding="utf-8")
        except UnicodeError as exc:
            raise WorkspaceError("Existing file is not valid UTF-8 text.") from exc
        if expected_content is None:
            raise WorkspaceError(
                "File already exists; read it and supply expected_content to replace it."
            )
        if actual_content != expected_content:
            raise WorkspaceError(
                "File changed since it was read; inspect it again before replacing."
            )
        return actual_content

    def delete_file(self, relative_path: str, confirmed: bool) -> str:
        if not confirmed:
            raise WorkspaceError("Explicit confirmation is required to delete a file.")
        path = self.resolve(relative_path)
        if path.is_symlink() or not path.is_file():
            raise WorkspaceError("Only existing regular files can be deleted.")
        if self._ignored(path.relative_to(self.root).as_posix()):
            raise WorkspaceError("Deleting excluded files is not permitted.")
        path.unlink()
        return path.relative_to(self.root).as_posix()

    def search(self, query: str, limit: int = 100) -> list[dict[str, object]]:
        if not query:
            raise WorkspaceError("Search query cannot be empty.")
        matches: list[dict[str, object]] = []
        for relative in self.list_files():
            try:
                content = self.read_file(relative)
            except WorkspaceError:
                continue
            for line_number, line in enumerate(content.splitlines(), 1):
                if query.casefold() in line.casefold():
                    matches.append(
                        {"path": relative, "line": line_number, "text": line[:500]}
                    )
                    if len(matches) >= limit:
                        return matches
        return matches
