import enum
import logging
import platform
import subprocess
import sys
import typing
from pathlib import Path

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

        if platform.system() == "Linux":
            self._setup_linux_runtime_monitoring()

    def infer_os_color_mode(self) -> OSColorMode:
        """
        Detect the OS color scheme using a 4-tier strategy:

        1. Qt 6.5+ official API (QStyleHints.colorScheme()) — works on macOS, Windows, KDE
        2. GNOME GSettings (subprocess) — works on GNOME 42+ where Qt API may return Unknown
        3. GTK settings files — works on XFCE, Cinnamon, Budgie, MATE
        4. QPalette threshold (QPalette::Base lightness < 128) — qBittorrent-style fallback
        """
        # Tier 1: Qt 6.5+ official API.
        # See: https://doc.qt.io/qt-6/qstylehints.html#colorScheme-prop
        # See: https://www.qt.io/blog/dark-mode-on-windows-11-with-qt-6.5
        try:
            color_scheme = self.styleHints().colorScheme()
            if color_scheme == QtCore.Qt.ColorScheme.Dark:
                return OSColorMode.DARK
            elif color_scheme == QtCore.Qt.ColorScheme.Light:
                return OSColorMode.LIGHT
        except AttributeError:
            # PySide2 / Qt < 6.5: QStyleHints.colorScheme() doesn't exist
            pass

        if platform.system() == "Linux":
            mode = self._infer_gnome_color_scheme()
            if mode is not None:
                return mode
            mode = self._infer_gtk_color_scheme()
            if mode is not None:
                return mode

        # Tier 4: Palette-based fallback.
        # Matches the approach used by qBittorrent's UIThemeManager:
        #     QPalette::Base.lightness() < 127  => Dark
        # See: https://github.com/qbittorrent/qBittorrent/blob/master/src/gui/uithememanager.cpp
        base_color = self.palette().color(QtGui.QPalette.Base)
        if base_color.lightness() < 128:
            return OSColorMode.DARK
        return OSColorMode.LIGHT

    def _infer_gnome_color_scheme(self) -> typing.Optional[OSColorMode]:
        """
        Read GNOME's color-scheme GSettings key directly.

        This is needed on GNOME 42+ where Qt's QStyleHints.colorScheme() may return
        Unknown because Qt's platform theme plugin doesn't monitor the new color-scheme
        key (it only monitors the legacy gtk-theme key).
        See: https://forum.qt.io/topic/145065/colorschemechanged-under-gnome
        """
        try:
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            if result.returncode == 0:
                scheme = result.stdout.strip().strip("'")
                if scheme == "prefer-dark":
                    return OSColorMode.DARK
                elif scheme == "prefer-light":
                    return OSColorMode.LIGHT
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
        return None

    def _infer_gtk_color_scheme(self) -> typing.Optional[OSColorMode]:
        """
        Check GTK settings files for dark mode preference.

        Reads ~/.config/gtk-{3,4}.0/settings.ini for:
        - gtk-application-prefer-dark-theme=1 (used by many GTK-based DEs)
        - gtk-theme-name containing '-dark' (e.g., "Adwaita-dark")

        The KDE plasma-integration platform theme uses a similar grayscale threshold
        on QPalette::Window to determine the color scheme:
            qGray(window.color().rgb()) < 192  => Dark
        See: https://invent.kde.org/plasma/plasma-integration/-/blob/master/qt6/src/platformtheme/khintssettings.cpp
        """
        for config_path in [
            Path.home() / ".config" / "gtk-4.0" / "settings.ini",
            Path.home() / ".config" / "gtk-3.0" / "settings.ini",
        ]:
            try:
                if not config_path.exists():
                    continue
                content = config_path.read_text()
                if "gtk-application-prefer-dark-theme=1" in content:
                    return OSColorMode.DARK
                for line in content.splitlines():
                    key_value = line.strip()
                    if key_value.lower().startswith("gtk-theme-name"):
                        theme = key_value.split("=", 1)[1].strip().strip('"').strip("'")
                        if theme.lower().endswith("-dark"):
                            return OSColorMode.DARK
            except OSError:
                pass
        return None

    def _setup_linux_runtime_monitoring(self) -> None:
        """
        Monitor for theme changes on Linux using a periodic timer.

        Re-checks the OS color scheme every 5 seconds and emits color_scheme_changed
        if it changes. This catches GNOME theme toggles at runtime, where Qt's
        ApplicationPaletteChange event may not fire.
        """
        self._theme_timer = QtCore.QTimer(self)
        self._theme_timer.timeout.connect(self._handle_palette_change)
        self._theme_timer.start(5000)

    def _handle_palette_change(self) -> None:
        """Handle system palette changes (e.g., dark/light mode toggle)."""
        new_mode = self.infer_os_color_mode()
        if new_mode != self.os_color_mode:
            log.debug(f"Color scheme changed from {self.os_color_mode} to {new_mode}")
            self.os_color_mode = new_mode
            self.color_scheme_changed.emit()


def setup_logging() -> None:
    logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
