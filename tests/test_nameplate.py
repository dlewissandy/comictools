"""THE NAMEPLATE ON THE DOOR: the browser tab is the studio's shingle.  A
NiceGUI app with no title reads "NiceGUI" in every tab and bookmark — the
author's own work, wearing the framework's name.  ui.run carries the title
and the favicon for every page at once, so there is exactly one place to
pin."""
import re


def _ui_run_call():
    src = open("main.py").read()
    m = re.search(r"ui\.run\((.*?)\)\s*$", src, re.S | re.M)
    assert m, "main.py must still stand the studio up with ui.run(...)"
    return m.group(1)


def test_the_tab_says_comic_studio():
    assert re.search(r"title\s*=\s*['\"]Comic Studio['\"]", _ui_run_call())


def test_the_tab_wears_a_glyph():
    """An emoji favicon needs no icon file and no static route — NiceGUI
    inlines it into the head as an SVG data URI."""
    assert re.search(r"favicon\s*=\s*['\"]\S+['\"]", _ui_run_call())
