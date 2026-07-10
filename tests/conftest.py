"""Shared fixtures: every test runs against a temp copy of data/ so the real
creative content is never touched (LocalStorage honors base_path)."""
import os
import shutil
import sys
import tempfile

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)


@pytest.fixture()
def tmp_data():
    """A disposable copy of the data directory; yields its path."""
    tmp = tempfile.mkdtemp()
    shutil.copytree(os.path.join(REPO, "data"), os.path.join(tmp, "data"))
    yield os.path.join(tmp, "data")
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture()
def storage(tmp_data):
    from storage.local import LocalStorage
    return LocalStorage(base_path=tmp_data)
