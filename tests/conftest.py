import pytest

from petmed_core import Core, create_session


@pytest.fixture
def core() -> Core:
    return Core(create_session())
