"""THE DEMO HOUSE: Foglamp Press — original work only, founded like any
real house, adopted in one click from an empty studio."""
import os
from types import SimpleNamespace


def test_adopting_founds_a_living_house(tmp_path, monkeypatch):
    import storage.registry as reg
    monkeypatch.setattr(reg, "REGISTRY_PATH", str(tmp_path / "registry.json"))
    monkeypatch.setattr(reg, "DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(os.path, "expanduser",
                        lambda p: p.replace("~", str(tmp_path)) if isinstance(p, str) and p.startswith("~") else p)

    import gui.home as home
    state = SimpleNamespace(thread=[], history=None, refresh_details=lambda: None,
                            render_your_turn=lambda: None, write=lambda: None)
    home.adopt_demo_house(state)

    houses = reg.registered()
    assert houses, "the demo house registered"
    st = reg.storage_for(houses[0]["slug"])
    from schema import Publisher, Series, Issue
    pubs = st.read_all_objects(Publisher)
    assert pubs and pubs[0].name == "Foglamp Press"
    ser = st.read_object(Series, {"series_id": "the-lighthouse-post"})
    assert ser is not None and ser.publisher_id == pubs[0].publisher_id
    iss = st.read_object(Issue, {"series_id": "the-lighthouse-post",
                                 "issue_id": "the-fog-edition"})
    assert iss is not None and "fog" in iss.story.lower()
    # founded like a real house: styles copied, git initialized
    house_dir = str(tmp_path / "git" / "foglamp-press-comics")
    assert os.path.isdir(os.path.join(house_dir, "styles"))
    assert os.path.isdir(os.path.join(house_dir, ".git"))
    # adopting twice never clobbers
    home.adopt_demo_house(state)
    assert len(st.read_all_objects(Publisher)) == 1


def test_the_demo_is_original_work():
    """No third-party IP, ever (standing ruling) — the demo speaks only
    its own names."""
    src = open("gui/home.py").read()
    demo = src[src.index("def adopt_demo_house"):]
    for banned in ("witchlight", "d&d", "dungeons", "marvel", "dc comics",
                   "disney", "batman", "spider"):
        assert banned not in demo.lower(), f"third-party name in the demo: {banned}"
    assert "Foglamp Press" in demo and "The Lighthouse Post" in demo
