"""EVERY HOUSE ITS OWN REPO: a git repository IS a publisher.

The studio keeps a small machine-local registry (~/.comic-studio/
publishers.json) of the publisher repos it knows.  ALL of them are
mounted at once: ./data is a real directory holding one symlink per
house (data/<slug> -> the repo), so every window sees every house and
there is no open-house state to trip over.  Repos stay self-contained —
their records hold 'data/…' locators relative to their OWN root, and
LocalStorage translates at the JSON boundary.

Git syncs the repos; the studio never becomes a version control system.
"""
from __future__ import annotations

import json
import os

from loguru import logger

REGISTRY_PATH = os.path.expanduser(os.path.join("~", ".comic-studio", "publishers.json"))
DATA_DIR = "data"


def _load() -> dict:
    try:
        with open(REGISTRY_PATH) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save(reg: dict) -> None:
    # the open-house concept is gone — a stale key must not linger
    reg.pop("open", None)
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    tmp = REGISTRY_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(reg, f, indent=1)
    os.replace(tmp, REGISTRY_PATH)


def registered() -> list[dict]:
    """Every publisher repo the studio knows: [{"slug", "path"}]."""
    return [p for p in _load().get("publishers", [])
            if os.path.isdir(os.path.expanduser(p.get("path", "")))]


def mount_path(slug: str) -> str:
    """Where the named house is mounted: data/<slug>."""
    return os.path.join(DATA_DIR, slug)


def _symlink(target: str, at: str) -> None:
    """A symlink on POSIX (and on Windows with Developer Mode), a junction
    on Windows without symlink privilege — junctions need no elevation and
    resolve identically for our use."""
    try:
        os.symlink(target, at, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        import _winapi
        _winapi.CreateJunction(target, at)


def _unmount(at: str) -> None:
    """Remove a mount itself, never its contents: os.remove for a symlink;
    os.rmdir for a Windows junction (deletes the reparse point only)."""
    if os.path.islink(at):
        os.remove(at)
    elif os.path.isdir(at) and os.path.realpath(at) != os.path.abspath(at):
        os.rmdir(at)


def mount_all() -> list[dict]:
    """MOUNT EVERY HOUSE (idempotent, runs at startup).

    Turns the legacy single-house symlink at ./data into a real directory,
    then ensures data/<slug> points at each registered repo.  Prunes ONLY
    symlinks that dangle or match no registered slug — a real file or
    directory under data/ is never touched (a half-migrated state stays
    visible instead of being destroyed).
    """
    if os.path.islink(DATA_DIR):
        os.remove(DATA_DIR)               # the old open-house mount retires
    elif os.path.isdir(DATA_DIR) and os.path.realpath(DATA_DIR) != os.path.abspath(DATA_DIR):
        os.rmdir(DATA_DIR)                # a Windows junction
    os.makedirs(DATA_DIR, exist_ok=True)

    houses = registered()
    want = {h["slug"]: os.path.realpath(os.path.expanduser(h["path"])) for h in houses}
    for slug, target in want.items():
        at = mount_path(slug)
        if os.path.islink(at):
            if os.path.realpath(at) != target:
                os.remove(at)
                _symlink(target, at)
        elif not os.path.exists(at):
            _symlink(target, at)
        # a real dir/file where a mount belongs: leave it — visible beats gone
    for entry in os.listdir(DATA_DIR):
        at = os.path.join(DATA_DIR, entry)
        if os.path.islink(at) and (entry not in want or not os.path.isdir(at)):
            os.remove(at)
    # THE PROSE LIVES IN MARKDOWN: every mounted house is migrated once
    # (inline JSON prose → .md sidecars) — so an adopted or cloned repo
    # from before the ruling reads correctly.
    for slug, target in want.items():
        _migrate_prose_once(slug, target)
    # a legacy single-root data/ (real files, not mounts) reads and writes
    # through the same sidecar hooks — it gets the same walk.  Markerless
    # (no .git of its own), so it re-walks each boot: instant once clean.
    legacy_series = os.path.join(DATA_DIR, "series")
    if os.path.isdir(legacy_series) and not os.path.islink(legacy_series):
        _migrate_prose_once("data", DATA_DIR)
    return houses


def _migrate_prose_once(slug: str, target: str) -> None:
    """Move a house's inline JSON prose into .md sidecars (idempotent).
    A marker in .git/ skips the walk on later boots; markerless houses
    (bare dirs, git-file worktrees) just re-walk — the walk converges."""
    marker = os.path.join(target, ".git", "comic-prose-v1")
    if os.path.isfile(marker):
        return
    from storage.local import migrate_house_prose
    try:
        n = migrate_house_prose(target)
        if n:
            logger.info(f"{slug}: moved prose to markdown sidecars in {n} files")
        if os.path.isdir(os.path.dirname(marker)):
            with open(marker, "w") as f:
                f.write("1\n")
    except Exception as ex:
        logger.warning(f"{slug}: prose migration skipped: {ex}")


def storage_for(slug: str):
    """A house-scoped LocalStorage rooted at the house's mount.  Repairs
    the mounts first if the one we need is missing — LocalStorage would
    otherwise mkdir a REAL directory where the symlink belongs."""
    from storage.local import LocalStorage
    at = mount_path(slug)
    if not os.path.isdir(at):
        mount_all()
    return LocalStorage(base_path=at)


def mounted_storages() -> list[tuple[str | None, "object"]]:
    """[(slug, storage)] for every registered house — what every fan-out
    view iterates.  Falls back to the legacy single-root layout when no
    registry exists."""
    from storage.local import LocalStorage
    houses = registered()
    if not houses:
        return [(None, LocalStorage(base_path=DATA_DIR))]
    return [(h["slug"], storage_for(h["slug"])) for h in houses]


def house_of_publisher(publisher_id: str) -> str | None:
    """The slug of the house holding the named publisher record."""
    from schema.publisher import Publisher
    for slug, st in mounted_storages():
        if slug is None:
            continue
        try:
            if st.read_object(Publisher, primary_key={"publisher_id": publisher_id}) is not None:
                return slug
        except Exception:
            continue
    return None


def house_of_series(series_id: str) -> str | None:
    """The slug of the house holding the named series — a directory probe,
    no JSON parse.  First hit wins (registry order)."""
    for h in registered():
        if os.path.isdir(os.path.join(mount_path(h["slug"]), "series", series_id)):
            return h["slug"]
    return None


def storage_for_key(pk: dict, fallback=None):
    """THE KEY NAMES ITS OWN HOUSE: a primary key carrying a series,
    publisher or style id resolves to the mount that actually holds it —
    regardless of where the author happens to be standing.  Returns
    `fallback` when no registered house claims the id (an unknown or
    hallucinated id stays subject to the caller's own discipline).

    THE CARNIVAL RULE: a fallback storage rooted OUTSIDE the mounts (a
    test fixture's tmp copy, a scratch clone) is never hijacked — fixture
    data shares real ids, and resolving would aim tool writes at the
    author's live repos."""
    if fallback is not None:
        base = str(getattr(fallback, "base_path", ""))
        if base and base != DATA_DIR and not base.startswith(DATA_DIR + os.sep):
            return fallback
    finders = (("series_id", house_of_series),
               ("publisher_id", house_of_publisher),
               ("style_id", house_of_style))
    if registered():
        for key, find in finders:
            if (pk or {}).get(key):
                slug = find(pk[key])
                if slug:
                    return storage_for(slug)
    return fallback


def house_of_style(style_id: str) -> str | None:
    """The slug of a house holding the named style.  FIRST HIT — bare
    style ids are ambiguous by design (default styles are copies sharing
    ids across houses); canonical style URLs carry the publisher, so this
    is only the legacy-link fallback."""
    for h in registered():
        if os.path.isdir(os.path.join(mount_path(h["slug"]), "styles", style_id)):
            return h["slug"]
    return None


def register(path: str, slug: str | None = None) -> str:
    """Add a publisher repo to the registry (idempotent) and mount it.
    Returns its slug."""
    path = os.path.abspath(os.path.expanduser(path))
    slug = slug or os.path.basename(path.rstrip(os.sep))
    reg = _load()
    pubs = [p for p in reg.get("publishers", []) if p.get("path") != path]
    pubs.append({"slug": slug, "path": path})
    reg["publishers"] = pubs
    _save(reg)
    if os.path.isdir(DATA_DIR) and not os.path.islink(DATA_DIR):
        at = mount_path(slug)
        if not os.path.exists(at):
            _symlink(os.path.realpath(path), at)
    # an adopted pre-ruling house must read correctly NOW, not after the
    # next restart — a save through the sidecar-only path would otherwise
    # zero its inline prose
    _migrate_prose_once(slug, os.path.realpath(path))
    return slug


def unregister(slug: str) -> bool:
    """Retire a house from the studio: the registry forgets it, its mount
    is removed, the repo on disk is NEVER touched.  An empty rack is legal
    — the wall renders its founding card."""
    reg = _load()
    pubs = [p for p in reg.get("publishers", []) if p.get("slug") != slug]
    if len(pubs) == len(reg.get("publishers", [])):
        return False
    reg["publishers"] = pubs
    _save(reg)
    _unmount(mount_path(slug))
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
    record, and a founding commit.  Registers (which mounts) and returns
    the slug."""
    import re
    import shutil
    import subprocess
    from storage.local import LocalStorage
    from schema.publisher import Publisher

    target_dir = os.path.abspath(os.path.expanduser(target_dir))
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "new-house"
    os.makedirs(os.path.join(target_dir, "series"), exist_ok=True)
    template_dir = template_dir or HOUSE_TEMPLATE
    # the app ships a template of its own (style definitions, prompts,
    # references) so a FRESH machine's first house is never styleless
    bundled = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "templates", "house")
    for sub in ("styles", "prompts", "references"):
        dst = os.path.join(target_dir, sub)
        if os.path.isdir(dst):
            continue
        houses = registered()
        sister = (os.path.join(os.path.realpath(os.path.expanduser(houses[0]["path"])), sub)
                  if houses else None)
        for src in (os.path.join(template_dir, sub), sister, os.path.join(bundled, sub)):
            if src and os.path.isdir(src):
                shutil.copytree(src, dst)
                break
    if not os.path.isdir(os.path.join(target_dir, "styles")):
        # REFUSE LOUDLY: the receipt promises 'the studio's default styles' —
        # founding a styleless house would make every first render a lie
        raise RuntimeError(
            "No styles source found (machine template, sister house, or app "
            "bundle) — cannot found a house without its styles.")
    LocalStorage(base_path=target_dir).create_object(
        Publisher(publisher_id=slug, name=name, description=None, logo=None))
    with open(os.path.join(target_dir, ".gitignore"), "w") as f:
        f.write(_HOUSE_GITIGNORE)
    if not os.path.isdir(os.path.join(target_dir, ".git")):
        subprocess.run(["git", "init", "-b", "main", "-q"], cwd=target_dir, check=True)
        subprocess.run(["git", "add", "-A"], cwd=target_dir, check=True)
        # a first-time author may have no git identity — the founding
        # commit must not fail raw (and the house registers regardless;
        # the commit can always be made later)
        ident = []
        probe = subprocess.run(["git", "config", "user.name"], cwd=target_dir,
                               capture_output=True, text=True)
        if not (probe.stdout or "").strip():
            ident = ["-c", "user.name=Comic Studio",
                     "-c", "user.email=studio@comic-studio.local"]
        try:
            subprocess.run(["git", *ident, "commit", "-q", "-m",
                            f"FOUNDING THE HOUSE: {name} — the studio's default styles, "
                            f"prompts and references, ready for its first series"],
                           cwd=target_dir, check=True)
        except subprocess.CalledProcessError as ex:
            logger.warning(f"founding commit deferred ({ex}) — the house still registers; "
                           f"commit when git is configured")
    return register(target_dir)
