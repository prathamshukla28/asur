import shutil

import pytest


@pytest.fixture(scope="session")
def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def pytest_collection_modifyitems(config, items):
    if shutil.which("ffmpeg") is not None:
        return
    skip = pytest.mark.skip(reason="ffmpeg binary not on PATH")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
