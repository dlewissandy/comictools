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


def _link_target() -> str | None:
    """The path ./data points at, when it is a mount of any kind — a POSIX
    symlink or a Windows junction.  None for a plain directory (the legacy
    single-studio layout) or nothing at all."""
    if not os.path.exists(DATA_LINK):
        return None
    real = os.path.realpath(DATA_LINK)
    if real == os.path.abspath(DATA_LINK):
        return None
    return real


def _unmount() -> None:
    """Remove the ./data mount itself, never its contents: os.remove for a
    symlink; os.rmdir for a Windows junction (which deletes the reparse
    point only)."""
    if os.path.islink(DATA_LINK):
        os.remove(DATA_LINK)
    elif os.path.isdir(DATA_LINK):
        os.rmdir(DATA_LINK)


def _mount(target: str) -> None:
    """Point ./data at target: a symlink on POSIX (and on Windows with
    Developer Mode), a junction on Windows without symlink privilege —
    junctions need no elevation and resolve identically for our use."""
    try:
        os.symlink(target, DATA_LINK, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        import _winapi
        _winapi.CreateJunction(target, DATA_LINK)


def open_slug() -> str | None:
    """The slug of the house ./data points at (None if data is a plain
    directory — the legacy single-studio layout)."""
    target = _link_target()
    if target is None:
        return None
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
    if os.path.exists(DATA_LINK) and _link_target() is None:
        return False
    _unmount()
    _mount(os.path.expanduser(target))
    reg = _load()
    reg["open"] = slug
    _save(reg)
    return True

def unregister(slug: str) -> bool:
    """Retire a house from the studio: the registry forgets it, the disk is
    NEVER touched.  Refuses to retire the open house while it is the only
    one — the studio must always stand somewhere."""
    reg = _load()
    pubs = [p for p in reg.get("publishers", []) if p.get("slug") != slug]
    if len(pubs) == len(reg.get("publishers", [])):
        return False
    if slug == open_slug():
        others = [p for p in pubs if os.path.isdir(os.path.expanduser(p.get("path", "")))]
        if not others:
            return False
        reg["publishers"] = pubs
        _save(reg)
        set_open(others[0]["slug"])   # the symlink re-points, nothing deleted
    else:
        reg["publishers"] = pubs
        _save(reg)
    return True


def looks_like_house(path: str) -> str | None:
    """If the directory already has a house's structure, the name of the
    publisher living there; else None."""
    path = os.path.expanduser(path)
    pubs_dir = os.path.join(path, "publishers")
    if not os.path.isdir(pubs_dir):
        return None
    if not (os.path.isdir(os.path.join(path, "series"))
            or os.path.isdir(os.path.join(path, "styles"))):
        return None
    from storage.local import LocalStorage
    from schema.publisher import Publisher
    recs = LocalStorage(base_path=path).read_all_objects(Publisher)
    return recs[0].name if recs else None


HOUSE_TEMPLATE = os.path.expanduser(os.path.join("~", ".comic-studio", "templates", "house"))

_HOUSE_GITIGNORE = """# working paper — the studio's local scratch, never history
.trash/
.queue/
.spend.json
**/exports/
**/.trash--*
.DS_Store
"""


def found_house(name: str, target_dir: str, template_dir: str | None = None) -> str:
    """FOUND A NEW HOUSE: a fresh git repo at target_dir carrying the
    studio's default styles, prompts and references, the publisher's own
    record, and a founding commit.  Registers and returns the slug."""
    import re
    import shutil
    import subprocess
    from storage.local import LocalStorage
    from schema.publisher import Publisher

    target_dir = os.path.abspath(os.path.expanduser(target_dir))
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "new-house"
    os.makedirs(os.path.join(target_dir, "series"), exist_ok=True)
    template_dir = template_dir or HOUSE_TEMPLATE
    for sub in ("styles", "prompts", "references"):
        src = os.path.join(template_dir, sub)
        dst = os.path.join(target_dir, sub)
        if os.path.isdir(src) and not os.path.isdir(dst):
            shutil.copytree(src, dst)
        elif not os.path.isdir(dst):
            # no template on this machine: the open house lends its copies
            fallback = os.path.join(os.path.realpath(DATA_LINK), sub)
            if os.path.isdir(fallback):
                shutil.copytree(fallback, dst)
    LocalStorage(base_path=target_dir).create_object(
        Publisher(publisher_id=slug, name=name, description=None, logo=None))
    with open(os.path.join(target_dir, ".gitignore"), "w") as f:
        f.write(_HOUSE_GITIGNORE)
    if not os.path.isdir(os.path.join(target_dir, ".git")):
        subprocess.run(["git", "init", "-b", "main", "-q"], cwd=target_dir, check=True)
        subprocess.run(["git", "add", "-A"], cwd=target_dir, check=True)
        subprocess.run(["git", "commit", "-q", "-m",
                        f"FOUNDING THE HOUSE: {name} — the studio's default styles, "
                        f"prompts and references, ready for its first series"],
                       cwd=target_dir, check=True)
    return register(target_dir)
