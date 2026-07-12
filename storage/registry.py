"""EVERY HOUSE ITS OWN REPO: a git repository IS a publisher.

The studio keeps a small machine-local registry (~/.comic-studio/
publishers.json) of the publisher repos it knows and which one is open.
The open house is mounted AT ./data — a symlink — so every path the
studio ever stored ('data/series/…' locators inside records included)
keeps resolving, and the app genuinely sees one publisher at a time.

Switching houses re-points the symlink; git syncs the repos; the studio
never becomes a version control system.
"""
from __future__ import annotations

import json
import os

REGISTRY_PATH = os.path.expanduser(os.path.join("~", ".comic-studio", "publishers.json"))
DATA_LINK = "data"


def _load() -> dict:
    try:
        with open(REGISTRY_PATH) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save(reg: dict) -> None:
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    tmp = REGISTRY_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(reg, f, indent=1)
    os.replace(tmp, REGISTRY_PATH)


def registered() -> list[dict]:
    """Every publisher repo the studio knows: [{"slug", "path"}]."""
    return [p for p in _load().get("publishers", [])
            if os.path.isdir(os.path.expanduser(p.get("path", "")))]


def open_slug() -> str | None:
    """The slug of the house ./data points at (None if data is a plain
    directory — the legacy single-studio layout)."""
    if not os.path.islink(DATA_LINK):
        return None
    target = os.path.realpath(DATA_LINK)
    for p in registered():
        if os.path.realpath(os.path.expanduser(p["path"])) == target:
            return p["slug"]
    return None


def register(path: str, slug: str | None = None) -> str:
    """Add a publisher repo to the registry (idempotent).  Returns its slug."""
    path = os.path.abspath(os.path.expanduser(path))
    slug = slug or os.path.basename(path.rstrip(os.sep))
    reg = _load()
    pubs = [p for p in reg.get("publishers", []) if p.get("path") != path]
    pubs.append({"slug": slug, "path": path})
    reg["publishers"] = pubs
    _save(reg)
    return slug


def set_open(slug: str) -> bool:
    """Point ./data at the named house.  Refuses to touch a real directory
    (the legacy layout must be migrated deliberately, never clobbered)."""
    target = next((p["path"] for p in registered() if p["slug"] == slug), None)
    if target is None:
        return False
    if os.path.exists(DATA_LINK) and not os.path.islink(DATA_LINK):
        return False
    if os.path.islink(DATA_LINK):
        os.remove(DATA_LINK)
    os.symlink(os.path.expanduser(target), DATA_LINK)
    reg = _load()
    reg["open"] = slug
    _save(reg)
    return True
