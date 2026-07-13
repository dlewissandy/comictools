"""THE PANEL'S TRUEST FACE: brief → rough → print.

A panel that has no featured print but HAS work on its light table shows
its ROUGH — the composed table (background, acetates, letters) — wherever
panels show their face: the open book's tiles and the bound proof.

The rough is composed once per table-arrangement signature and cached
beside the panel's figures, so book repaints stay instant.
"""
from __future__ import annotations

import hashlib
import json
import os

from loguru import logger


def rough_signature(board, scene=None) -> str | None:
    """A stamp of everything that shapes the rough — None when the table
    holds nothing composable (then the brief is the panel's face)."""
    blk = board.figure_blocking or {}

    def on(key, default=1):
        return bool((blk.get(key) or {}).get('on', default))

    parts = [board.aspect.value]
    live = False
    for key, path in sorted((board.figure_images or {}).items()):
        if not (path and os.path.exists(path) and on(key)):
            continue
        live = True
        try:
            parts.append(f"{key}={os.path.basename(path)}@{os.path.getmtime(path):.0f}")
        except OSError:
            parts.append(f"{key}={os.path.basename(path)}")
    if not live:
        return None
    parts.append(json.dumps(blk, sort_keys=True, default=str))
    for d in (getattr(board, 'dialogue', None) or []):
        parts.append(f"d:{d.text}")
    for n in (getattr(board, 'narration', None) or []):
        parts.append(f"n:{n.text}")
    if scene is not None:
        parts.append(f"set:{getattr(scene, 'setting_id', None)}|{getattr(scene, 'style_id', None)}")
    return hashlib.md5("\n".join(parts).encode()).hexdigest()[:16]


def rough_face(storage, board, scene=None) -> str | None:
    """The panel's rough as a cached image path — or None when the table
    holds nothing (the brief is the face then)."""
    sig = rough_signature(board, scene)
    if sig is None:
        return None
    from storage.filepath import obj_to_imagepath
    figures_dir = os.path.join(
        os.path.dirname(obj_to_imagepath(obj=board, base_path=storage.base_path)), "figures")
    cached = os.path.join(figures_dir, f".rough-face-{sig}.jpg")
    if os.path.exists(cached):
        return cached
    try:
        # compose lazily through the same code the inker receives — the
        # face the book shows IS the rough the render will start from
        from agentic.tools.imaging import _compose_table_rough
        raw = _compose_table_rough(storage, board, scene)
        if raw is None or not os.path.exists(raw):
            return None
        from PIL import Image
        img = Image.open(raw).convert('RGB')
        os.makedirs(figures_dir, exist_ok=True)
        # older faces of this board make way for the current one
        for f in os.listdir(figures_dir):
            if f.startswith('.rough-face-'):
                try:
                    os.remove(os.path.join(figures_dir, f))
                except OSError:
                    pass
        img.save(cached, 'JPEG', quality=88)
        try:
            os.remove(raw)          # the uuid intermediate never piles up
        except OSError:
            pass
        return cached
    except Exception as ex:
        logger.warning(f"rough face skipped for {getattr(board, 'id', '?')}: {ex}")
        return None
