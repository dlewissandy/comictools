"""THE TRADE DRESS: the metadata a printed comic wears — the credits strip,
the issue-number badge, the price box.  Not plain lettering: bordered,
offset, stamped ON TOP of the art the way real covers wear them.

Each piece is an acetate keyed 'dress/<piece>' in the board's
figure_blocking.  The TEXT is drawn from the issue's metadata and
SNAPSHOTTED into the blocking entry when toggled on (and refreshed at each
bench paint), so the compositor prints exactly what the rough shows without
reaching for the Issue record.
"""

# key -> (label for the rail, letter kind for the compositor)
DRESS_PIECES = {
    "dress/credits": ("Credits", "credit"),
    "dress/issue":   ("Issue №", "badge"),
    "dress/price":   ("Price", "badge"),
}

# covers wear the full dress; panels may carry attribution (a credits strip)
COVER_PIECES = ("dress/credits", "dress/issue", "dress/price")
PANEL_PIECES = ("dress/credits",)

# defaults: corner box tradition — № top-left, price top-right,
# credits along the bottom
DRESS_DEFAULTS = {
    "dress/credits": {"x": 4, "y": 3, "fs": 8},
    "dress/issue":   {"x": 4, "y": 90, "fs": 12},
    "dress/price":   {"x": 88, "y": 90, "fs": 10},
}


def dress_text(issue, key: str) -> str | None:
    """The piece's words, drawn from the issue's metadata.  None when the
    metadata isn't there to speak (an unpriced issue has no price box)."""
    if issue is None:
        return None
    if key == "dress/credits":
        bits = []
        if getattr(issue, "writer", None):
            bits.append(f"STORY · {issue.writer}")
        if getattr(issue, "artist", None):
            bits.append(f"ART · {issue.artist}")
        if getattr(issue, "colorist", None):
            bits.append(f"COLORS · {issue.colorist}")
        if getattr(issue, "creative_minds", None):
            bits.append(f"MINDS · {issue.creative_minds}")
        return "   ".join(bits).upper() or None
    if key == "dress/issue":
        n = getattr(issue, "issue_number", None)
        return f"No. {n}" if n is not None else None
    if key == "dress/price":
        # free text, printed verbatim — '$3.99', 'Free', '10¢'
        p = getattr(issue, "price", None)
        return str(p) if p else None
    return None


def refresh_dress_text(storage, board, issue) -> bool:
    """Keep the snapshots honest: metadata edited after the toggle reaches
    the board on its next paint.  Returns True when something changed."""
    blk = getattr(board, "figure_blocking", None) or {}
    changed = False
    for key in DRESS_PIECES:
        b = blk.get(key)
        if not b:
            continue
        text = dress_text(issue, key)
        if text and b.get("text") != text:
            b["text"] = text
            changed = True
    if changed:
        storage.update_object(board)
    return changed


def collect_dress(blk: dict | None) -> list[dict]:
    """The board's trade-dress letters, compositor-shaped: read from the
    blocking snapshots alone (the print never reaches for the Issue)."""
    out = []
    for key, (_label, kind) in DRESS_PIECES.items():
        b = (blk or {}).get(key)
        if not b or not b.get("on", 1):
            continue
        text = (b.get("text") or "").strip()
        if not text:
            continue
        d = DRESS_DEFAULTS[key]
        out.append({"kind": kind, "text": text,
                    "x": b.get("x", d["x"]), "y": b.get("y", d["y"]),
                    "fs": b.get("fs", d["fs"])})
    return out
