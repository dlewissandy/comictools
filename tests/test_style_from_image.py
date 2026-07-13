"""CREATE A STYLE FROM PREVIOUS ART: the studio reads the art/character/bubble
styles off a picture and KEEPS the image as the style's art exemplar — nothing
else renders."""
import asyncio
import json
import os
from types import SimpleNamespace

from PIL import Image

import gui.routes as routes
import helpers.generator as generator
from agentic.tools.creator import create_style_from_image
from schema import ComicStyle


def test_create_style_from_image_keeps_art_exemplar(storage, tmp_data, monkeypatch):
    # borrow a real style's structured fields as the mocked vision extraction,
    # so the ComicStyle validates exactly as a real one would
    src = storage.read_all_objects(ComicStyle)[0]

    class _Extract:
        description = "A borrowed hand for the test."
        art_style = src.art_style
        character_style = src.character_style
        bubble_styles = src.bubble_styles
    monkeypatch.setattr(generator, "invoke_generate_api", lambda *a, **k: _Extract())
    # avoid the selection-trail plumbing in a headless test
    monkeypatch.setattr(routes, "style_ancestry", lambda storage, sid: [])

    art = os.path.join(tmp_data, "prev-art.png")
    Image.new("RGB", (40, 30), (90, 60, 30)).save(art)

    state = SimpleNamespace(storage=storage, selection=[], is_dirty=False,
                            change_selection=lambda new=None: None)
    wrapper = SimpleNamespace(context=state)
    note = asyncio.run(create_style_from_image.on_invoke_tool(
        wrapper, json.dumps({"name": "Test Woodcut", "image_locator": art})))

    assert "from the art" in str(note)
    made = [s for s in storage.read_all_objects(ComicStyle) if s.name == "Test Woodcut"]
    assert made, "the style was created"
    st = made[0]
    # the picture is kept as the style's art exemplar, re-filed into its own store
    assert isinstance(st.image, dict) and st.image.get("art")
    assert os.path.exists(st.image["art"])
    assert st.image["art"] != art                       # the style's own copy
    assert st.description == "A borrowed hand for the test."


def test_create_style_from_image_rejects_missing_file(storage, monkeypatch):
    state = SimpleNamespace(storage=storage, selection=[], is_dirty=False,
                            change_selection=lambda new=None: None)
    wrapper = SimpleNamespace(context=state)
    note = asyncio.run(create_style_from_image.on_invoke_tool(
        wrapper, json.dumps({"name": "Nope", "image_locator": "/no/such/art.png"})))
    assert "not found" in str(note)
