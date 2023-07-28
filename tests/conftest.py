import typing

import pytest

from dangerzone.gui import Application


# Use this fixture to make `pytest-qt` invoke our custom QApplication.
# See https://pytest-qt.readthedocs.io/en/latest/qapplication.html#testing-custom-qapplications
@pytest.fixture(scope="session")
def qapp_cls() -> typing.Type[Application]:
    return Application
