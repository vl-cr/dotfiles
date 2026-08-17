#!/usr/bin/env python3

"""Install and merge the dotfiles Codex hook without clobbering other hooks."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import sys
import tempfile


STATUS_MESSAGE = "Checking for destructive commands"
MATCHER = "^Bash$"
TIMEOUT_SECONDS = 5
GUARD_PREFIX = "dotfiles_destructive_commands_"
CONTENT_ADDRESSED_GUARD = re.compile(
    rf"^{re.escape(GUARD_PREFIX)}[0-9a-f]{{16}}\.py$"
)
LEGACY_COMMAND = ("python3", "~/.codex/hooks/destructive_commands.py")


class InstallError(RuntimeError):
    """Raised when existing Codex data cannot be preserved safely."""


def _guard_destination(codex_home: Path, guard_data: bytes) -> Path:
    digest = hashlib.sha256(guard_data).hexdigest()[:16]
    return codex_home / "hooks" / f"{GUARD_PREFIX}{digest}.py"


def _handler_command(python_executable: Path, guard_destination: Path) -> str:
    if not python_executable.is_absolute() or not guard_destination.is_absolute():
        raise InstallError("hook executables must use absolute paths")
    return shlex.join((str(python_executable), str(guard_destination)))


def _is_owned_handler(
    handler: object, matcher: object, codex_home: Path
) -> bool:
    if matcher not in {"Bash", MATCHER}:
        return False
    if not isinstance(handler, dict):
        return False
    if handler.get("type") != "command":
        return False
    if handler.get("statusMessage") != STATUS_MESSAGE:
        return False
    command = handler.get("command")
    if not isinstance(command, str):
        return False
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    if len(words) != 2:
        return False
    if tuple(words) == LEGACY_COMMAND:
        return True
    interpreter, script = map(Path, words)
    expected_parent = codex_home / "hooks"
    return (
        interpreter.is_absolute()
        and script.is_absolute()
        and script.parent == expected_parent
        and CONTENT_ADDRESSED_GUARD.fullmatch(script.name) is not None
    )


def _validate_hook_document(document: object) -> dict[str, object]:
    if not isinstance(document, dict):
        raise InstallError("hooks.json must contain a JSON object")
    hooks = document.get("hooks")
    if hooks is None:
        return document
    if not isinstance(hooks, dict):
        raise InstallError("hooks.json 'hooks' must be an object")
    for event, groups in hooks.items():
        if not isinstance(event, str) or not isinstance(groups, list):
            raise InstallError("each hook event must contain a list")
        for group in groups:
            if not isinstance(group, dict):
                raise InstallError("each hook group must be an object")
            handlers = group.get("hooks")
            if not isinstance(handlers, list):
                raise InstallError("each hook group must contain a hooks list")
            if any(not isinstance(handler, dict) for handler in handlers):
                raise InstallError("each hook handler must be an object")
    return document


def merge_hook_document(
    document: dict[str, object], command: str, codex_home: Path
) -> dict[str, object]:
    """
    Merge one namespaced handler while retaining unrelated data and order.

    Args:
        > document (dict[str, object]):
            Parsed existing hook manifest.
        > command (str):
            Absolute, shell-quoted command for the installed guard.

    Returns:
        - dict[str, object]: A deep-copied merged manifest.

    Raises:
        - InstallError: When an existing hook shape cannot be preserved safely.
    """
    merged = copy.deepcopy(_validate_hook_document(document))
    hooks = merged.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise InstallError("hooks.json 'hooks' must be an object")
    groups = hooks.setdefault("PreToolUse", [])
    if not isinstance(groups, list):
        raise InstallError("PreToolUse hooks must be a list")

    handler = {
        "type": "command",
        "command": command,
        "timeout": TIMEOUT_SECONDS,
        "statusMessage": STATUS_MESSAGE,
    }
    replacement_group = {"matcher": MATCHER, "hooks": [handler]}
    rebuilt: list[object] = []
    inserted = False

    for group in groups:
        if not isinstance(group, dict):
            raise InstallError("each PreToolUse group must be an object")
        handlers = group.get("hooks")
        if not isinstance(handlers, list):
            raise InstallError("each PreToolUse group must contain a hooks list")
        owned_indexes = [
            index
            for index, existing in enumerate(handlers)
            if _is_owned_handler(existing, group.get("matcher"), codex_home)
        ]
        if not owned_indexes:
            rebuilt.append(group)
            continue

        if not inserted and len(handlers) == 1:
            updated_group = copy.deepcopy(group)
            updated_group["matcher"] = MATCHER
            updated_group["hooks"] = [handler]
            rebuilt.append(updated_group)
            inserted = True
            continue

        retained = [
            existing
            for index, existing in enumerate(handlers)
            if index not in owned_indexes
        ]
        if retained:
            updated_group = copy.deepcopy(group)
            updated_group["hooks"] = retained
            rebuilt.append(updated_group)
        if not inserted:
            rebuilt.append(replacement_group)
            inserted = True

    if not inserted:
        rebuilt.append(replacement_group)
    hooks["PreToolUse"] = rebuilt
    return merged


def _read_document(path: Path, template: Path | None) -> tuple[dict[str, object], int]:
    source = path if path.exists() or path.is_symlink() else template
    if source is None:
        return {
            "description": "Block destructive shell commands before execution.",
            "hooks": {},
        }, 0o600
    try:
        raw = source.read_text(encoding="utf-8")
        document = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InstallError(f"cannot safely read {source}: {error}") from error
    validated = _validate_hook_document(document)
    if path.is_symlink() or not path.exists():
        mode = 0o600
    else:
        mode = stat.S_IMODE(path.stat().st_mode)
    return validated, mode


def _install_guard(data: bytes, destination: Path) -> None:
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file():
            raise InstallError(f"refusing to replace unrelated path: {destination}")
        if destination.read_bytes() != data:
            raise InstallError(f"guard digest collision at: {destination}")
        destination_stat = destination.stat()
        if destination_stat.st_nlink != 1:
            raise InstallError(f"refusing to reuse linked guard path: {destination}")
        if stat.S_IMODE(destination_stat.st_mode) != 0o600:
            destination.chmod(0o600)
        return

    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent, prefix=f".{destination.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o600)
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if destination.is_symlink() or destination.read_bytes() != data:
                raise InstallError(f"guard path changed during installation: {destination}")
    finally:
        temporary.unlink(missing_ok=True)


def _write_document(path: Path, document: dict[str, object], mode: int) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    encoded = (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode()
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def install_hooks(
    codex_home: Path,
    guard_source: Path,
    python_executable: Path,
    template: Path | None = None,
) -> Path:
    """
    Install a content-addressed guard and merge its Codex hook definition.

    Args:
        > codex_home (Path):
            Destination Codex home directory.
        > guard_source (Path):
            Reviewed Python guard source.
        > python_executable (Path):
            Python 3.12+ interpreter recorded in the hook command.
        > template (Path | None):
            Hook manifest used only when no destination manifest exists.

    Returns:
        - Path: Content-addressed installed guard path.

    Raises:
        - InstallError: When inputs or existing data cannot be handled safely.
    """
    codex_home = codex_home.expanduser().absolute()
    guard_source = guard_source.expanduser().resolve(strict=True)
    python_executable = python_executable.expanduser().resolve(strict=True)
    running_python = Path(sys.executable).resolve(strict=True)
    if sys.version_info < (3, 12) or python_executable != running_python:
        raise InstallError(
            "the recorded interpreter must be the Python 3.12+ interpreter "
            "running this installer"
        )
    if not guard_source.is_file():
        raise InstallError(f"guard source is not a regular file: {guard_source}")
    if not python_executable.is_file():
        raise InstallError(f"Python executable is not a regular file: {python_executable}")

    hooks_path = codex_home / "hooks.json"
    try:
        guard_data = guard_source.read_bytes()
        compile(guard_data, str(guard_source), "exec")
    except (OSError, SyntaxError, ValueError) as error:
        raise InstallError(f"guard source is not valid Python: {error}") from error

    destination = _guard_destination(codex_home, guard_data)
    command = _handler_command(python_executable, destination)
    existing, mode = _read_document(hooks_path, template)
    merged = merge_hook_document(existing, command, codex_home)

    _install_guard(guard_data, destination)
    if merged != existing or not hooks_path.exists() or hooks_path.is_symlink():
        _write_document(hooks_path, merged, mode)
    return destination


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", type=Path, required=True)
    parser.add_argument("--guard-source", type=Path, required=True)
    parser.add_argument("--python", dest="python_executable", type=Path, required=True)
    parser.add_argument("--template", type=Path)
    return parser.parse_args()


def main() -> None:
    """Install the hook or report a preservation-safe error."""
    if sys.version_info < (3, 12):
        raise SystemExit("Codex hook installation requires Python 3.12 or newer")
    arguments = _arguments()
    try:
        destination = install_hooks(
            arguments.codex_home,
            arguments.guard_source,
            arguments.python_executable,
            arguments.template,
        )
    except (InstallError, OSError) as error:
        raise SystemExit(f"Codex hook installation failed: {error}") from error
    print(f"Installed Codex destructive-command guard: {destination}")


if __name__ == "__main__":
    main()
