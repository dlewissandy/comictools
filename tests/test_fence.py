"""THE FENCE: a test process must never see the author's real rack.

The dangerous moment is COLLECTION, not the tests themselves: importing a
test module can import app modules (test_ui_send imports main), and main's
import runs mount_all — which mounts and MIGRATES every registered house.
The fence in conftest.py blinds the registry process-wide before any test
module loads, so that boot walk finds an empty rack and scratch paths."""
import os

# ---- collection-time proof -------------------------------------------------
# These lines run at IMPORT, at the same moment main's mount_all would run.
# If the fence is down, they fail the whole collection loudly.
from storage import registry as _reg

_REAL_RACK = os.path.expanduser(os.path.join("~", ".comic-studio", "publishers.json"))
assert os.path.abspath(_reg.REGISTRY_PATH) != os.path.abspath(_REAL_RACK), \
    "the fence is down: a test process can see the author's real rack"
assert _reg.DATA_DIR != "data", \
    "the fence is down: mounts would land in the repo's live data/ dir"
assert _reg.registered() == [], \
    "the fence is down: the registry still lists real houses"


def test_the_rack_stays_fenced_inside_tests(tmp_path):
    from storage import registry
    assert registry.registered() == []
    assert os.path.abspath(registry.REGISTRY_PATH) != os.path.abspath(_REAL_RACK)


def test_mount_all_under_the_fence_touches_no_house():
    """The exact call main.py makes at import: with the fence up it mounts
    nothing, migrates nothing, and returns an empty rack."""
    from storage import registry
    assert registry.mount_all() == []
    assert os.listdir(registry.DATA_DIR) == []


def test_the_fixture_pin_survives_the_fence():
    """fixture_source() pinned the copy source BEFORE the fence went up,
    and the pin must reach BOTH copies of the conftest module (pytest
    imports it as 'conftest' and as 'tests.conftest')."""
    from tests.conftest import fixture_source
    src = fixture_source()
    assert os.path.isdir(src), f"fixture source vanished: {src}"
    assert os.path.basename(src.rstrip(os.sep)) != "data", \
        "the pin fell back to ./data — it resolved after the fence went up"
