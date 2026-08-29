#!/usr/bin/env python3
"""Load Helium's public bang registry into a compact local cache."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from typing import Any
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


SERVICE_URL = "https://services.helium.imput.net/bangs.json"
CACHE_TTL_SECONDS = 24 * 60 * 60
MAX_DOWNLOAD_BYTES = 16 * 1024 * 1024
_TRIGGER = re.compile(r"^[a-z0-9._-]+$")
_TRAILING_COMMA = re.compile(r",(?=\s*[}\]])")
_BANG_QUERY = re.compile(r"^!([a-z0-9._-]+)(?:\s+([\s\S]*))?$", re.IGNORECASE)
_SEARCH_PLACEHOLDERS = ("{searchTerms}", "{{{s}}}", "{{s}}", "%s")


def cache_path() -> Path:
    cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache_home / "omarchy-search" / "bangs.json"


def parse_jsonc(raw: str) -> Any:
    without_comments = "\n".join(
        line for line in raw.splitlines() if not line.lstrip().startswith("//")
    )
    return json.loads(_TRAILING_COMMA.sub("", without_comments))


def compact_registry(entries: Any) -> dict[str, list[str]]:
    if not isinstance(entries, list):
        raise ValueError("bang registry root must be an array")

    bangs: dict[str, list[str]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        label = entry.get("s")
        template = entry.get("u")
        if not isinstance(label, str) or not isinstance(template, str):
            continue
        if urlsplit(template).scheme.lower() not in {"http", "https"}:
            continue

        triggers: list[Any] = []
        primary = entry.get("t")
        if isinstance(primary, str):
            triggers.append(primary)
        aliases = entry.get("ts")
        if isinstance(aliases, list):
            triggers.extend(aliases)

        for value in triggers:
            if not isinstance(value, str):
                continue
            trigger = value.strip().lower()
            if not _TRIGGER.fullmatch(trigger):
                continue
            bangs.setdefault(trigger, [label, template])

    if not bangs:
        raise ValueError("bang registry contained no usable triggers")
    return bangs


def read_cache(path: Path) -> tuple[int, dict[str, list[str]]] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("version") != 1:
        return None
    updated_at = payload.get("updatedAt")
    bangs = payload.get("bangs")
    if not isinstance(updated_at, int) or not isinstance(bangs, dict) or not bangs:
        return None
    return updated_at, bangs


def write_cache(path: Path, updated_at: int, bangs: dict[str, list[str]]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = {"version": 1, "updatedAt": updated_at, "bangs": bangs}
    fd, temporary = tempfile.mkstemp(prefix=".bangs.", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def fetch_registry() -> dict[str, list[str]]:
    request = Request(SERVICE_URL, headers={"User-Agent": "omarchy-search/1.0"})
    with urlopen(request, timeout=10) as response:
        raw = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(raw) > MAX_DOWNLOAD_BYTES:
        raise ValueError("bang registry exceeded download limit")
    return compact_registry(parse_jsonc(raw.decode("utf-8")))


def load_registry(path: Path | None = None, now: int | None = None) -> dict[str, list[str]]:
    target = path or cache_path()
    timestamp = int(time.time()) if now is None else now
    cached = read_cache(target)
    if cached and timestamp - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    try:
        bangs = fetch_registry()
        write_cache(target, timestamp, bangs)
        return bangs
    except Exception as error:
        if cached:
            print(f"bang registry refresh failed; using stale cache: {error}", file=sys.stderr)
            return cached[1]
        print(f"bang registry unavailable: {error}", file=sys.stderr)
        return {}


def resolve_query(
    query: str, registry: dict[str, list[str]]
) -> dict[str, str] | None:
    normalized = query.strip()
    match = _BANG_QUERY.fullmatch(normalized)
    if not match:
        return None

    trigger = match.group(1).lower()
    row = registry.get(trigger)
    if not isinstance(row, list) or len(row) < 2:
        return None

    label, template = row[0], row[1]
    if not isinstance(label, str) or not isinstance(template, str):
        return None
    if urlsplit(template).scheme.lower() not in {"http", "https"}:
        return None

    terms = (match.group(2) or "").strip()
    url = ""
    if terms:
        encoded = quote(terms, safe="")
        url = template
        for placeholder in _SEARCH_PLACEHOLDERS:
            if placeholder in url:
                url = url.replace(placeholder, encoded)
                break

    return {
        "query": normalized,
        "trigger": trigger,
        "label": label,
        "template": template,
        "terms": terms,
        "url": url,
    }

def match_triggers(
    prefix: str, registry: dict[str, list[str]], limit: int = 8
) -> list[dict[str, str]]:
    normalized = prefix.strip().lower()
    if not normalized or not _TRIGGER.fullmatch(normalized) or limit <= 0:
        return []

    triggers = sorted(
        (trigger for trigger in registry if trigger.startswith(normalized)),
        key=lambda trigger: (trigger != normalized, len(trigger), trigger),
    )
    matches: list[dict[str, str]] = []
    seen_destinations: set[tuple[str, str]] = set()
    for trigger in triggers:
        row = registry.get(trigger)
        if not isinstance(row, list) or len(row) < 2:
            continue
        label, template = row[0], row[1]
        if not isinstance(label, str) or not isinstance(template, str):
            continue
        if urlsplit(template).scheme.lower() not in {"http", "https"}:
            continue

        destination = (label.casefold(), template)
        if destination in seen_destinations:
            continue
        seen_destinations.add(destination)
        matches.append(
            {"trigger": trigger, "label": label, "template": template}
        )
        if len(matches) == limit:
            break
    return matches




def main() -> int:
    registry = load_registry()
    if len(sys.argv) == 1:
        payload: Any = registry
    elif len(sys.argv) == 3 and sys.argv[1] == "--resolve":
        payload = resolve_query(sys.argv[2], registry)
    elif len(sys.argv) == 3 and sys.argv[1] == "--match":
        payload = match_triggers(sys.argv[2], registry)
    else:
        print(
            f"usage: {Path(sys.argv[0]).name} [--resolve QUERY | --match PREFIX]",
            file=sys.stderr,
        )
        return 2

    json.dump(payload, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
