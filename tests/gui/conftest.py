import os
import typing
from collections.abc import Generator
from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from pytestqt.qtbot import QtBot

# FIXME: See https://github.com/freedomofpress/dangerzone/issues/320 for more details.
if typing.TYPE_CHECKING:
    from PySide2 import QtCore, QtWidgets
else:
    try:
        from PySide6 import QtCore, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtWidgets


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--onscreen",
        action="store_true",
        default=False,
        help="Run GUI tests with the system display instead of offscreen rendering",
    )


def pytest_configure(config: pytest.Config) -> None:
    if not config.getoption("--onscreen", default=False):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.hookimpl(wrapper=True, trylast=True)
def pytest_runtest_teardown(item: pytest.Item) -> Generator[None, object, object]:
    """Destroy the Qt objects that a GUI test leaves behind.

    By the time a GUI test is over, pytest-qt has called `close()` and `deleteLater()`
    on every widget registered with `qtbot.addWidget()`, and has run `processEvents()`
    a few times. That is not enough to actually destroy them:

    * `deleteLater()` merely posts a DeferredDelete event, and Qt delivers those only
      from within a running event loop. There is none at teardown time, so the
      deletions pile up unprocessed.
    * The widgets that the application creates without a parent, such as
      `MainWindow.file_dialog` or the various `Alert` dialogs, are not registered with
      pytest-qt in the first place.

    The result is that a Qt test leaves roughly a dozen live widgets behind, and since
    pytest holds on to the fixtures that reference them for the whole session, they are
    only ever destroyed by the interpreter's final garbage collection pass -- in an
    order that PySide does not control, and possibly after the QApplication itself is
    gone. On Windows this occasionally faults *after* pytest has already reported the
    test as passed, which fails the CI run with no indication of which test process
    died.

    So we destroy them here instead, while the QApplication is still alive and we are
    still in control of the ordering.

    See more in https://github.com/freedomofpress/dangerzone/issues/493
    """
    result = yield

    # NOTE: `instance()` returns None for the tests that never create a QApplication,
    # even though the PySide2 stubs that we type-check against say otherwise.
    app = QtWidgets.QApplication.instance()
    if app is not None:
        # Let the fixtures' teardown settle first. Closing the main window starts the
        # application's shutdown sequence, and this delivers the signals that its
        # shutdown thread queued up, so that they do not arrive at a half-deleted
        # widget tree.
        app.processEvents()

        # NOTE: Do not call close() on the widgets here. Closing the main window runs
        # `MainWindow.closeEvent()`, which kicks off the shutdown sequence *again* and
        # creates more Qt objects than it destroys.
        for widget in app.topLevelWidgets():
            widget.deleteLater()

        # Deliver the DeferredDelete events that we, and pytest-qt before us, just
        # posted. `processEvents()` alone would skip them.
        QtCore.QCoreApplication.sendPostedEvents(
            None, int(QtCore.QEvent.Type.DeferredDelete)
        )
        app.processEvents()

    return result


def pytest_collection_modifyitems(items: list) -> None:
    for item in items:
        if Path(item.fspath).is_relative_to(Path(__file__).parent):
            item.add_marker(pytest.mark.xdist_group("gui"))


from dangerzone.gui.logic import DangerzoneGui
from dangerzone.isolation_provider.dummy import Dummy


@pytest.fixture
def dangerzone_gui(
    qtbot: QtBot, mocker: MockerFixture, tmp_path: Path
) -> DangerzoneGui:
    mock_app = mocker.MagicMock()
    dummy = mocker.MagicMock(spec=Dummy)
    return DangerzoneGui(mock_app, dummy)
