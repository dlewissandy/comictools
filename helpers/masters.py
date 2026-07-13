"""THE MASTERS' KEYS: a setting's master backgrounds, keyed by style AND
orientation — a portrait cover's re-ink must never clobber the landscape
master every landscape panel shares.

Key format: '<style_id>' for landscape (the classic establishing view and
every legacy entry), '<style_id>/portrait' and '<style_id>/square' for the
others.  Readers ask for the board's own orientation first, then borrow any
orientation of the right style — and say when they borrowed.
"""
import os


def orientation_of(aspect) -> str:
    a = getattr(aspect, "value", aspect) or "landscape"
    return a if a in ("landscape", "portrait", "square") else "landscape"


def master_key(style_id: str, aspect) -> str:
    o = orientation_of(aspect)
    return style_id if o == "landscape" else f"{style_id}/{o}"


def master_for(setting, style_id: str, aspect) -> tuple[str | None, bool]:
    """(image_path, exact) — exact is False when we borrowed another
    orientation's master (the caller should volunteer that truth)."""
    imgs = getattr(setting, "images", None) or {}
    if not style_id:
        img = next((i for i in imgs.values() if i and os.path.exists(i)), None)
        return img, False
    k = master_key(style_id, aspect)
    img = imgs.get(k)
    if img and os.path.exists(img):
        return img, True
    for kk, vv in imgs.items():
        if (kk == style_id or kk.startswith(style_id + "/")) and vv and os.path.exists(vv):
            return vv, False
    return None, False


def split_key(key: str) -> tuple[str, str]:
    """'vintage-four-color/portrait' -> (style_id, orientation)."""
    if "/" in key:
        sid, o = key.rsplit("/", 1)
        if o in ("portrait", "square"):
            return sid, o
    return key, "landscape"
