import pytest

from asur.core.binaries import ffmpeg_path


@pytest.fixture(scope="session")
def ffmpeg_available() -> bool:
    return ffmpeg_path() is not None


def pytest_collection_modifyitems(config, items):
    if ffmpeg_path() is not None:
        return
    skip = pytest.mark.skip(reason="ffmpeg binary not found (PATH or ASUR_FFMPEG)")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
