"""
THE COMPOSITOR: one PIL pass that lays acetates over a base exactly the way
the light table displays them.  Flattening the table, merging a group down,
and composing the rough the inker finishes all share this math — one
implementation, no drift.
"""
import os

DIMS = {"landscape": (1536, 1024), "portrait": (1024, 1536), "square": (1024, 1024)}
PAPER = (250, 246, 236, 255)


def base_canvas(aspect: str, background: str | None, transparent: bool = False):
    """The board's base: the background scaled-to-cover and center-cropped,
    else blank paper (or full transparency for merge-downs with no plate)."""
    from PIL import Image
    W, H = DIMS[aspect]
    if background and os.path.exists(background):
        base = Image.open(background).convert('RGBA')
        s = max(W / base.width, H / base.height)
        base = base.resize((max(1, round(base.width * s)), max(1, round(base.height * s))))
        left, top = (base.width - W) // 2, (base.height - H) // 2
        return base.crop((left, top, left + W, top + H))
    return Image.new('RGBA', DIMS[aspect], (0, 0, 0, 0) if transparent else PAPER)


def paste_acetates(base, aspect: str, layers) -> list[tuple]:
    """Paste acetates in z order, exactly as the rough displays them.

    layers: iterable of (path, blocking) where blocking holds x (percent from
    left, figure center), y (percent up from the bottom), h (height as
    percent of the frame), z, and flip.  Returns each pasted box
    (L, T, R, B) in canvas pixels, in paste order.
    """
    from PIL import Image
    W, H = DIMS[aspect]
    boxes = []
    for path, b in sorted(layers, key=lambda pb: pb[1].get('z', 0)):
        img = Image.open(path).convert('RGBA')
        if b.get('flip'):
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        th = H * float(b.get('h', 60)) / 100
        s = th / img.height
        img = img.resize((max(1, round(img.width * s)), max(1, round(th))))
        cx = W * float(b.get('x', 50)) / 100
        bottom = H - H * float(b.get('y', 0)) / 100
        base.paste(img, (round(cx - img.width / 2), round(bottom - img.height)), img)
        boxes.append((cx - img.width / 2, bottom - img.height, cx + img.width / 2, bottom))
    return boxes
