import enum
import logging
import sys
import typing

# FIXME: See https://github.com/freedomofpress/dangerzone/issues/320 for more details.
if typing.TYPE_CHECKING:
    from PySide2 import QtCore, QtGui, QtWidgets
else:
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtGui, QtWidgets

from ..util import get_resource_path

log = logging.getLogger(__name__)


class OSColorMode(enum.Enum):
    """
    Operating system color mode, e.g. Light or Dark Mode on macOS 10.14+ or Windows 10+.

    The enum values are used as the names of Qt properties that will be selected by QSS
    property selectors to set color-mode-specific style rules.
    """

    LIGHT = "light"
    DARK = "dark"


class Application(QtWidgets.QApplication):
    document_selected = QtCore.Signal(list)
    application_activated = QtCore.Signal()
    color_scheme_changed = QtCore.Signal()

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super(Application, self).__init__(*args, **kwargs)
        self.setQuitOnLastWindowClosed(False)
        with get_resource_path("dangerzone.css").open("r") as f:
            style = f.read()
        self.setStyleSheet(style)

        # Needed under certain windowing systems to match the application to the
        # desktop entry in order to display the correct application name and icon
        # and to allow identifying windows that belong to the application (e.g.
        # under Wayland it sets the correct app ID). The value is the name of the
        # Dangerzone .desktop file.
        self.setDesktopFileName("press.freedom.dangerzone")

        # In some combinations of window managers and OSes, if we don't set an
        # application name, then the window manager may report it as `python3` or
        # `__init__.py`. Always set this to `dangerzone`, which corresponds to the
        # executable name as well.
        # See: https://github.com/freedomofpress/dangerzone/issues/402
        self.setApplicationName("dangerzone")

        self.original_event = self.event

        def monkeypatch_event(arg__1: QtCore.QEvent) -> bool:
            event = arg__1  # oddly Qt calls internally event by "arg__1"
            # In macOS, handle the file open event
            if isinstance(event, QtGui.QFileOpenEvent):
                # Skip file open events in dev mode
                if not hasattr(sys, "dangerzone_dev"):
                    self.document_selected.emit([event.file()])
                    return True
            elif event.type() == QtCore.QEvent.ApplicationActivate:
                self.application_activated.emit()
                return True
            elif event.type() == QtCore.QEvent.Type.ApplicationPaletteChange:
                self._handle_palette_change()
                return True

            return self.original_event(event)

        self.event = monkeypatch_event  # type: ignore [method-assign]

        self.os_color_mode = self.infer_os_color_mode()
        log.debug(f"Inferred system color scheme as {self.os_color_mode}")

    def infer_os_color_mode(self) -> OSColorMode:
        """
        Qt 6.5+ explicitly provides the OS color scheme via QStyleHints.colorScheme(),
        but we still need to support PySide2/Qt 5, so instead we infer the OS color
        scheme from the default palette.
        """
        text_color, window_color = (
            self.palette().color(role)
            for role in (QtGui.QPalette.WindowText, QtGui.QPalette.Window)
        )
        if text_color.lightness() > window_color.lightness():
            return OSColorMode.DARK
        return OSColorMode.LIGHT

    def _handle_palette_change(self) -> None:
        """Handle system palette changes (e.g., dark/light mode toggle)."""
        new_mode = self.infer_os_color_mode()
        if new_mode != self.os_color_mode:
            log.debug(f"Color scheme changed from {self.os_color_mode} to {new_mode}")
            self.os_color_mode = new_mode
            self.color_scheme_changed.emit()


def setup_logging() -> None:
    logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
