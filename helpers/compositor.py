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


def is_placeholder(text: str | None) -> bool:
    """Scaffold text the table lays down before the author writes — it must
    never reach a composite, a render brief, or the printed book."""
    return bool(text) and text.strip().rstrip('…').strip().lower() in ("say something", "narration")


def letter_blocks(text: str | None, cap: int = 8) -> list[str]:
    """A text insert's letters: the blank-line-separated blocks of its
    description — each block is one letter acetate on the table."""
    import re
    return [b.strip() for b in re.split(r'\n\s*\n', text or '') if b.strip()][:cap]


def collect_letters(board) -> list[dict]:
    """The board's letters with their table blocking resolved — the same
    defaults the rough displays, so a composite matches what the author saw.
    Letters the author switched off and unwritten placeholders are skipped
    (the guard against printing the table's training wheels)."""
    from helpers.trade_dress import collect_dress
    dress = collect_dress(getattr(board, 'figure_blocking', None))
    if not hasattr(board, 'dialogue'):
        # THE MAILBAG's letter blocks are captions; other inserts keep their
        # description as a render BRIEF only — production notes must never
        # print as letters
        if getattr(board, 'kind', None) == 'mailbag' and getattr(board, 'description', None):
            blk = getattr(board, 'figure_blocking', None) or {}
            blocks = letter_blocks(board.description)
            step = 84 / max(len(blocks), 1)
            letters = []
            for i, text in enumerate(blocks):
                b = blk.get(f'letterblock/{i}') or {}
                if not b.get('on', 1):
                    continue
                letters.append({"kind": "caption", "text": text,
                                "x": b.get('x', 8), "y": b.get('y', max(88 - i * step, 4)),
                                "fs": b.get('fs', 11)})
            return letters + dress
        return dress
    blk = getattr(board, 'figure_blocking', None) or {}

    def b_of(key):
        return blk.get(key) or {}

    letters = []
    narration = getattr(board, 'narration', None) or []
    for pos, defaults, cap in (('top', lambda i: (2, 88 - i * 12), 2),
                               ('bottom', lambda i: (2, 4), 1)):
        for i, n in enumerate([n for n in narration if n.position.value == pos][:cap]):
            b = b_of(f'caption/{pos}/{i}')
            if not b.get('on', 1) or is_placeholder(n.text):
                continue
            dx, dy = defaults(i)
            letters.append({"kind": "caption", "text": n.text,
                            "x": b.get('x', dx), "y": b.get('y', dy), "fs": b.get('fs', 11)})
    for i, d in enumerate((getattr(board, 'dialogue', None) or [])[:4]):
        b = b_of(f'balloon/{i}')
        if not b.get('on', 1) or is_placeholder(d.text):
            continue
        # the balloon hangs near its speaker when they're on the table
        speaker = next((b_of(f"{r.character_id}/{r.variant_id}")
                        for r in (getattr(board, 'character_references', None) or [])
                        if r.character_id == d.character_id), {})
        x = b.get('x', speaker.get('x', 25 + 22 * i))
        y = b.get('y', 72 - (i % 2) * 14)
        letters.append({"kind": "balloon", "text": d.text, "x": x, "y": y,
                        "fs": b.get('fs', 11), "emphasis": d.emphasis.value,
                        "tx": b.get('tx', x), "ty": b.get('ty', max(y - 14, 2))})
    return letters + dress


def _letter_font(size: int):
    """Comic lettering when the system has it, sans otherwise."""
    from PIL import ImageFont
    for name in ("Comic Sans MS.ttf", "Chalkboard.ttc", "Helvetica.ttc", "Arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def paste_letters(base, aspect: str, letters: list[dict]) -> None:
    """Draw caption boxes and balloons over the composite the way the rough
    shows them: left/bottom-anchored percents, font scaled to the canvas,
    speech tails aimed where the author dragged them."""
    from PIL import ImageDraw
    if not letters:
        return
    W, H = DIMS[aspect]
    draw = ImageDraw.Draw(base)
    INK = (28, 26, 23, 255)

    def wrap(text, font, max_w):
        lines, line = [], ""
        for word in text.split():
            trial = f"{line} {word}".strip()
            if draw.textlength(trial, font=font) <= max_w or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        return lines + ([line] if line else [])

    for L in letters:
        emphasis = L.get('emphasis', '')
        # LETTERS PRINT WHAT YOU BLOCK: fs means "px on a 520px-tall canvas"
        # on both sides of the glass; no hidden multipliers — the author
        # sizes shouts and effects by hand and the print honors it
        px = max(14, round(float(L.get('fs', 11)) * H / 520))
        font = _letter_font(px)
        lines = wrap(L['text'], font, W * (0.34 if L['kind'] == 'balloon' else 0.56))
        line_h = round(px * 1.3)
        text_w = max(draw.textlength(l, font=font) for l in lines)
        pad = round(px * 0.7)
        x0 = W * float(L['x']) / 100
        if L['kind'] != 'caption':
            # balloons hang CENTERED on x, exactly as the rough shows them
            x0 -= (text_w + 2 * pad) / 2
        y1 = H - H * float(L['y']) / 100          # the letter's bottom edge
        box = (x0, y1 - line_h * len(lines) - 2 * pad, x0 + text_w + 2 * pad, y1)

        if L['kind'] == 'credit':
            # THE CREDITS STRIP: a paper band with an ink shadow offset —
            # trade dress stands OFF the art, never melts into it
            off = max(3, px // 4)
            draw.rectangle([box[0] + off, box[1] + off, box[2] + off, box[3] + off],
                           fill=INK)
            draw.rectangle(box, fill=(250, 246, 236, 255), outline=INK, width=3)
        elif L['kind'] == 'badge':
            # THE CORNER BADGE: issue number and price wear a heavy stamp
            off = max(3, px // 4)
            draw.rectangle([box[0] + off, box[1] + off, box[2] + off, box[3] + off],
                           fill=INK)
            draw.rectangle(box, fill=(252, 216, 56, 255), outline=INK, width=5)
        elif L['kind'] == 'caption':
            draw.rectangle(box, fill=(253, 244, 198, 255), outline=INK, width=3)
        elif emphasis == 'sound effect':
            pass                                   # raw display lettering, no bubble
        elif L['kind'] not in ('credit', 'badge'):
            radius = min(round(px * 1.2), round((box[3] - box[1]) / 2))
            tip = (W * float(L.get('tx', L['x'])) / 100, H - H * float(L.get('ty', 0)) / 100)
            cx = (box[0] + box[2]) / 2
            if emphasis == 'thought':
                # a chain of shrinking thought-puffs toward the thinker
                for t, r in ((0.35, px * 0.45), (0.65, px * 0.3), (0.9, px * 0.18)):
                    px_, py_ = cx + (tip[0] - cx) * t, box[3] + (tip[1] - box[3]) * t
                    draw.ellipse([px_ - r, py_ - r, px_ + r, py_ + r],
                                 fill=(255, 255, 255, 255), outline=INK, width=2)
            elif tip[1] > box[3]:
                draw.polygon([(cx - px * 0.6, box[3] - 2), (cx + px * 0.6, box[3] - 2), tip],
                             fill=(255, 255, 255, 255), outline=INK)
            outline_w = 5 if emphasis == 'shout' else 2 if emphasis == 'whisper' else 3
            draw.rounded_rectangle(box, radius=radius, fill=(255, 255, 255, 255),
                                   outline=INK, width=outline_w)
            if emphasis != 'thought' and tip[1] > box[3]:
                # reopen the bubble where the tail leaves it
                draw.polygon([(cx - px * 0.6 + 3, box[3] - outline_w),
                              (cx + px * 0.6 - 3, box[3] - outline_w),
                              (cx, box[3] + 2)], fill=(255, 255, 255, 255))

        fill = (110, 106, 100, 255) if emphasis == 'whisper' else INK
        stroke = {}
        if emphasis == 'sound effect':
            # display lettering has no bubble to read against — knock it out
            # of the art with comic-yellow fill and a heavy ink stroke
            fill = (252, 216, 56, 255)
            stroke = {"stroke_width": max(3, px // 6), "stroke_fill": INK}
        ty0 = box[1] + pad
        for line in lines:
            lw = draw.textlength(line, font=font)
            draw.text(((box[0] + box[2] - lw) / 2, ty0), line, font=font, fill=fill, **stroke)
            ty0 += line_h


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
        rot = float(b.get('rot') or 0)
        if rot:
            # CSS rotates around the element's center — pivot the same way:
            # keep the pre-tilt center, expand the canvas so nothing crops
            cy = bottom - th / 2
            img = img.rotate(-rot, expand=True, resample=Image.BICUBIC)
            base.paste(img, (round(cx - img.width / 2), round(cy - img.height / 2)), img)
            boxes.append((cx - img.width / 2, cy - img.height / 2,
                          cx + img.width / 2, cy + img.height / 2))
        else:
            base.paste(img, (round(cx - img.width / 2), round(bottom - img.height)), img)
            boxes.append((cx - img.width / 2, bottom - img.height, cx + img.width / 2, bottom))
    return boxes
