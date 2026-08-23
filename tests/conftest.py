import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ["CACHE_FILE"] = str(pathlib.Path(__file__).parent / "fixture_cache.json")

import pytest

import frontend


@pytest.fixture
def client():
    frontend.cache.clear()
    return frontend.app.test_client()
