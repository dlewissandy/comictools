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
