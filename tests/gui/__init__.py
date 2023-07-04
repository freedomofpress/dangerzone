from pathlib import Path
from typing import Optional
from unittest import mock

import pytest
from pytest import MonkeyPatch
from pytest_mock import MockerFixture

from dangerzone import util
from dangerzone.gui import Application
from dangerzone.gui.logic import DangerzoneGui
from dangerzone.gui.updater import UpdaterThread
from dangerzone.isolation_provider.dummy import Dummy


def generate_isolated_updater(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    app_mocker: MockerFixture,
) -> UpdaterThread:
    """Generate an Updater class with its own settings."""
    app = app_mocker.MagicMock()

    dummy = Dummy()
    # XXX: We can monkey-patch global state without wrapping it in a context manager, or
    # worrying that it will leak between tests, for two reasons:
    #
    # 1. Parallel tests in PyTest take place in different processes.
    # 2. The monkeypatch fixture tears down the monkey-patch after each test ends.
    monkeypatch.setattr(util, "get_config_dir", lambda: tmp_path)
    dangerzone = DangerzoneGui(app, isolation_provider=dummy)
    updater = UpdaterThread(dangerzone)
    return updater


@pytest.fixture
def updater(
    tmp_path: Path, monkeypatch: MonkeyPatch, mocker: MockerFixture
) -> UpdaterThread:
    return generate_isolated_updater(tmp_path, monkeypatch, mocker)
