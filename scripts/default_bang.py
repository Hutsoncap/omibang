#!/usr/bin/env python3
"""Persist a menu-wide default after validating it against Helium's registry."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any

try:
    from . import bangs
except ImportError:
    import bangs


def config_path() -> Path:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_home / "omarchy" / "extensions" / "omarchy-search.json"


def read_config(path: Path) -> dict[str, Any]:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return {"version": 1}
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError(f"refusing to read non-regular config: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"invalid search config: {path}") from error
    if not isinstance(payload, dict):
        raise RuntimeError(f"search config root must be an object: {path}")
    return payload


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise RuntimeError(f"refusing to write through symlinked directory: {path.parent}")

    existing = None
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        metadata = None
    if metadata is not None:
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError(f"refusing to replace non-regular config: {path}")
        existing = path.read_bytes()

    data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, stat.S_IMODE(metadata.st_mode) if metadata else 0o600)
        if existing is not None:
            backup = path.with_name(path.name + ".bak")
            backup_fd, backup_temporary = tempfile.mkstemp(
                prefix=f".{backup.name}.", dir=path.parent
            )
            backup_temporary_path = Path(backup_temporary)
            try:
                with os.fdopen(backup_fd, "wb") as handle:
                    handle.write(existing)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(backup_temporary_path, 0o600)
                os.replace(backup_temporary_path, backup)
            finally:
                backup_temporary_path.unlink(missing_ok=True)
        os.replace(temporary_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary_path.unlink(missing_ok=True)


def set_default(
    trigger: str,
    *,
    path: Path | None = None,
    registry: dict[str, list[str]] | None = None,
) -> str:
    normalized = trigger.strip().lower()
    catalog = registry if registry is not None else bangs.load_registry()
    row = catalog.get(normalized)
    if not row or len(row) < 2:
        raise ValueError(f"!{normalized} is not in Helium's bang catalog")

    target = path or config_path()
    payload = read_config(target)
    payload["version"] = 1
    payload["defaultBang"] = normalized
    atomic_write(target, payload)
    return str(row[0])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("set", "get"))
    parser.add_argument("trigger", nargs="?")
    args = parser.parse_args()

    target = config_path()
    if args.command == "get":
        print(read_config(target).get("defaultBang", "ddg"))
        return 0
    if not args.trigger:
        parser.error("set requires a bang shorthand")
    try:
        label = set_default(args.trigger, path=target)
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"default_bang.py: {error}\n")
    print(label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
