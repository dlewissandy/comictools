

def test_rotation_pivots_the_center(tmp_path):
    """A tilted acetate composites the way CSS shows it: pivoting around the
    element's center, expanded so nothing crops."""
    from PIL import Image
    from helpers.compositor import DIMS, base_canvas, paste_acetates
    art = str(tmp_path / "bar.png")
    Image.new("RGBA", (400, 100), (200, 30, 30, 255)).save(art)

    W, H = DIMS["landscape"]
    blocking = {"x": 50, "y": 40, "h": 10}
    flat = base_canvas("landscape", None)
    (fb,) = paste_acetates(flat, "landscape", [(art, blocking)])
    tilted = base_canvas("landscape", None)
    (tb,) = paste_acetates(tilted, "landscape", [(art, {**blocking, "rot": 90})])

    # same center either way — rotation never teleports the acetate
    fc = ((fb[0] + fb[2]) / 2, (fb[1] + fb[3]) / 2)
    tc = ((tb[0] + tb[2]) / 2, (tb[1] + tb[3]) / 2)
    assert abs(fc[0] - tc[0]) < 2 and abs(fc[1] - tc[1]) < 2
    # a 90-degree tilt swaps the box proportions
    assert (tb[3] - tb[1]) > (tb[2] - tb[0])
    # red pixels stand vertical at the pivot
    cx, cy = round(tc[0]), round(tc[1])
    assert tilted.getpixel((cx, cy - int(H * 0.08)))[0] > 150
    assert tilted.getpixel((cx, cy + int(H * 0.08)))[0] > 150
