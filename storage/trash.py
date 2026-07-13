"""
The studio trash: deletes are moves, not destruction.

Every deleted object folder (or image file) is moved into
{base_path}/.trash/<entry>/ with a manifest recording where it came from, so
'undo my last delete' is always possible.  Creative work is never rm -rf'd.
"""
import json
import os
import shutil
import time
from uuid import uuid4

from loguru import logger

TRASH_DIR = ".trash"


def soft_delete(base_path: str, path: str, note: str = "") -> str:
    """
    Move a file or folder into the trash.  Returns the trash entry directory.
    """
    entry = os.path.join(base_path, TRASH_DIR, f"{int(time.time() * 1000)}-{uuid4().hex[:8]}")
    os.makedirs(entry, exist_ok=True)
    payload = os.path.join(entry, "payload")
    shutil.move(path, payload)
    manifest = {"original_path": path, "deleted_at": time.time(), "note": note,
                "is_dir": os.path.isdir(payload)}
    json.dump(manifest, open(os.path.join(entry, "manifest.json"), "w"), indent=2)
    logger.info(f"soft-deleted {path} -> {entry}")
    return entry


def soft_backup(base_path: str, path: str, note: str = "") -> str:
    """
    COPY a file into the trash (the original stays in place) — the studio's
    pre-overwrite insurance.  Returns the trash entry directory.
    """
    entry = os.path.join(base_path, TRASH_DIR, f"{int(time.time() * 1000)}-{uuid4().hex[:8]}")
    os.makedirs(entry, exist_ok=True)
    payload = os.path.join(entry, "payload")
    if os.path.isdir(path):
        shutil.copytree(path, payload)
    else:
        shutil.copy2(path, payload)
    manifest = {"original_path": path, "deleted_at": time.time(), "note": note,
                "is_dir": os.path.isdir(payload)}
    json.dump(manifest, open(os.path.join(entry, "manifest.json"), "w"), indent=2)
    logger.info(f"soft-backed-up {path} -> {entry}")
    return entry


def _restores_inside(base_path: str, rel_original: str) -> bool:
    """A manifest records its original as a CWD-relative path.  A basket
    that was COPIED elsewhere (a test fixture, a backup) must never restore
    into the tree it was copied FROM — the landing spot has to sit under
    THIS basket's own base."""
    base = os.path.normpath(os.path.abspath(base_path))
    target = os.path.normpath(os.path.abspath(rel_original))
    return target == base or target.startswith(base + os.sep)


def restore_last(base_path: str) -> str | None:
    """
    Restore the most recent trash entry to its original location.
    Returns the restored path, or None if the trash is empty or the original
    location is occupied again.
    """
    trash_root = os.path.join(base_path, TRASH_DIR)
    if not os.path.isdir(trash_root):
        return None

    entries = sorted(os.listdir(trash_root), reverse=True)
    for name in entries:
        entry = os.path.join(trash_root, name)
        manifest_path = os.path.join(entry, "manifest.json")
        if not os.path.isfile(manifest_path):
            continue
        manifest = json.load(open(manifest_path))
        original = manifest["original_path"]
        if not _restores_inside(base_path, original):
            logger.warning(f"skipping trash entry for {original}: it would land outside this basket's base")
            continue
        if os.path.exists(original):
            # this entry was superseded (something lives at its path again —
            # e.g. layout pages rewritten under the same ids) — keep walking
            # back to the newest entry that CAN be restored
            logger.info(f"skipping trash entry for {original}: path exists again")
            continue
        os.makedirs(os.path.dirname(original), exist_ok=True)
        shutil.move(os.path.join(entry, "payload"), original)
        shutil.rmtree(entry, ignore_errors=True)
        logger.info(f"restored {original}")
        return original
    return None


def list_entries(base_path: str, limit: int = 60) -> list[dict]:
    """The wastebasket's contents, newest first: what was struck, from
    where, and when — the truth that makes 'bring it back' possible."""
    trash_root = os.path.join(base_path, TRASH_DIR)
    if not os.path.isdir(trash_root):
        return []
    out = []
    for name in sorted(os.listdir(trash_root), reverse=True)[: limit * 2]:
        manifest_path = os.path.join(trash_root, name, "manifest.json")
        if not os.path.isfile(manifest_path):
            continue
        try:
            m = json.load(open(manifest_path))
        except (json.JSONDecodeError, OSError):
            continue
        out.append({"entry": name, "original_path": m.get("original_path", ""),
                    "deleted_at": m.get("deleted_at", 0), "note": m.get("note", ""),
                    "occupied": os.path.exists(m.get("original_path", ""))})
        if len(out) >= limit:
            break
    return out


def restore_entry(base_path: str, entry: str) -> str | None:
    """Restore ONE named wastebasket entry to its original place.  Returns
    the restored path, or None (missing entry / the place is occupied)."""
    entry_dir = os.path.join(base_path, TRASH_DIR, entry)
    manifest_path = os.path.join(entry_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        return None
    manifest = json.load(open(manifest_path))
    original = manifest["original_path"]
    if not _restores_inside(base_path, original):
        logger.warning(f"cannot restore {original}: it would land outside this basket's base")
        return None
    if os.path.exists(original):
        logger.warning(f"cannot restore {original}: path exists again")
        return None
    os.makedirs(os.path.dirname(original), exist_ok=True)
    shutil.move(os.path.join(entry_dir, "payload"), original)
    shutil.rmtree(entry_dir, ignore_errors=True)
    logger.info(f"restored {original}")
    return original


def purge(base_path: str, older_than_days: float = 30) -> int:
    """Empty wastebasket entries older than the given age.  Returns the
    number of entries destroyed — the ONLY place the studio truly deletes."""
    trash_root = os.path.join(base_path, TRASH_DIR)
    if not os.path.isdir(trash_root):
        return 0
    cutoff = time.time() - older_than_days * 86400
    n = 0
    for name in os.listdir(trash_root):
        manifest_path = os.path.join(trash_root, name, "manifest.json")
        try:
            m = json.load(open(manifest_path))
        except (OSError, json.JSONDecodeError):
            continue
        if m.get("deleted_at", 0) < cutoff:
            shutil.rmtree(os.path.join(trash_root, name), ignore_errors=True)
            n += 1
    logger.info(f"purged {n} wastebasket entries older than {older_than_days}d")
    return n
