"""THE FEEL KNOBS: four aesthetic dials on the auto-flow — density, verticality,
irregularity, variety.  Each moves only UNLOCKED panels; a locked panel is
always honored; and all-neutral reproduces the plain flow exactly."""
from helpers.pagination import paginate
from helpers.tilings import PIECE_PANEL


def _panels(n, aspect="square", size="1x", **feel):
    return [{"aspect": aspect, "size": size, "locked": False, "feel": feel}
            for _ in range(n)]


def _mixed(n, **feel):
    s = [("square", "1x"), ("landscape", "1x"), ("portrait", "1x"), ("square", "2x")]
    return [{"aspect": s[i % 4][0], "size": s[i % 4][1], "locked": False, "feel": feel}
            for i in range(n)]


def _avg_page(pages):
    return sum(len(p["indices"]) for p in pages) / len(pages)


def _portrait_share(pages):
    pcs = [c for p in pages for c in p["pieces"]]
    return sum(1 for (_x, _y, w, h) in pcs if h > w) / len(pcs)


def _avg_cv(pages):
    def cv(pieces):
        a = [w * h for (_x, _y, w, h) in pieces]
        m = sum(a) / len(a)
        return (sum((v - m) ** 2 for v in a) / len(a)) ** 0.5 / m if m else 0.0
    return sum(cv(p["pieces"]) for p in pages) / len(pages)


def _repeats(pages):
    sig = [tuple(sorted(PIECE_PANEL[(w, h)] for (_x, _y, w, h) in p["pieces"])) for p in pages]
    return sum(1 for i in range(1, len(sig)) if sig[i] == sig[i - 1])


def test_neutral_feel_reproduces_the_plain_flow():
    plain = paginate([{"aspect": "landscape", "size": "1x", "locked": False} for _ in range(20)])
    zeroed = paginate(_panels(20, "landscape", "1x",
                              density=0, verticality=0, irregularity=0, variety=0))
    assert plain == zeroed


def test_density_scales_panels_per_page():
    sparse = _avg_page(paginate(_mixed(30, density=-1.0)))
    neutral = _avg_page(paginate(_mixed(30)))
    dense = _avg_page(paginate(_mixed(30, density=1.0)))
    assert sparse < neutral < dense           # fewer big pages -> many small ones


def test_verticality_biases_portrait_vs_landscape():
    tall = _portrait_share(paginate(_panels(24, "square", "1x", verticality=1.0)))
    wide = _portrait_share(paginate(_panels(24, "square", "1x", verticality=-1.0)))
    assert tall > wide


def test_irregularity_raises_size_variance():
    dynamic = _avg_cv(paginate(_panels(24, "square", "1x", irregularity=1.0)))
    grid = _avg_cv(paginate(_panels(24, "square", "1x", irregularity=-1.0)))
    assert dynamic > grid


def test_variety_breaks_consecutive_repeats():
    plain = _repeats(paginate(_panels(30, "landscape", "1x")))
    varied = _repeats(paginate(_panels(30, "landscape", "1x", variety=1.0)))
    assert plain >= 2 and varied < plain      # identical pages -> broken up


def test_transformations_expand_the_pool_and_feed_variety():
    # the flow uses ALL tilings (mirror/rotation twins), not just the 354
    # canonical ones the human picker leafs through
    from helpers.tilings import all_tilings, swatch_book
    from helpers.pagination import _best_page, _sig
    assert len(all_tilings()) > len(swatch_book()) * 2   # ~1125 vs 354

    # and variety can reach a DIFFERENT-geometry twin at the SAME flex — free
    # visual variety, a mirror of the same shapes
    shapes = (("landscape", "1x"), ("portrait", "1x"), ("square", "1x"),
              ("landscape", "1x"), ("square", "1x"), ("portrait", "1x"), ("landscape", "1x"))
    locks = (False,) * len(shapes)
    feel = {"density": 0, "verticality": 0, "irregularity": 0, "variety": 1.0}
    best = _best_page(shapes, locks, feel)
    twin = _best_page(shapes, locks, feel, avoid_sig=_sig(best[2]))
    assert _sig(twin[2]) != _sig(best[2])       # a different arrangement
    assert twin[1] == best[1]                    # at no extra flex


def test_a_knob_never_overrides_a_lock():
    # a locked landscape-2x panel keeps its 6x4 even under a maxed verticality
    # knob (which otherwise pulls hard toward portrait); 5 panels, since a 6x4
    # can only ride a 4- or 5-panel page
    ps = _panels(5, "square", "1x", verticality=1.0)
    ps[0] = {"aspect": "landscape", "size": "2x", "locked": True,
             "feel": {"verticality": 1.0}}
    pages = paginate(ps)
    pg = next(p for p in pages if 0 in p["indices"])
    piece = pg["pieces"][pg["indices"].index(0)]
    assert (piece[2], piece[3]) == (6, 4)     # the lock wins over the knob
