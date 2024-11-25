import platform
import subprocess
from unittest import mock

import pytest

from dangerzone.gui.logic import DangerzoneGui

if platform.system() == "Linux":
    from xdg.DesktopEntry import DesktopEntry, ParsingError


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux-only test")
def test_order_mime_handers() -> None:
    """
    Given a default mime handler returned by xdg-mime,
    ensure it is the first item available in the list
    of compatible applications.
    """
    mock_app = mock.MagicMock()
    dummy = mock.MagicMock()

    mock_desktop = mock.MagicMock(spec=DesktopEntry)
    mock_desktop.getMimeTypes.return_value = "application/pdf"
    mock_desktop.getExec.side_effect = [
        "/usr/bin/madeup-evince",
        "/usr/local/bin/madeup-mupdf",
        "/usr/local/bin/madeup-libredraw",
    ]
    mock_desktop.getName.side_effect = [
        "Evince",
        "MuPDF",
        "LibreOffice",
    ]

    with (
        mock.patch(
            "subprocess.check_output", return_value=b"libreoffice-draw.desktop"
        ) as mock_default_mime_hander,
        mock.patch(
            "os.listdir",
            side_effect=[
                ["org.gnome.Evince.desktop"],
                ["org.pwmt.zathura-pdf-mupdf.desktop"],
                ["libreoffice-draw.desktop"],
            ],
        ) as mock_list,
        mock.patch("dangerzone.gui.logic.DesktopEntry", return_value=mock_desktop),
    ):
        dz = DangerzoneGui(mock_app, dummy)

        mock_default_mime_hander.assert_called_once_with(
            ["xdg-mime", "query", "default", "application/pdf"]
        )
        mock_list.assert_called()
        assert len(dz.pdf_viewers) == 3
        assert dz.pdf_viewers.popitem(last=False)[0] == "LibreOffice"


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux-only test")
def test_mime_handers_succeeds_no_default_found() -> None:
    """
    Given a failure to return default mime handler,
    ensure compatible applications are still returned.
    """
    mock_app = mock.MagicMock()
    dummy = mock.MagicMock()

    mock_desktop = mock.MagicMock(spec=DesktopEntry)
    mock_desktop.getMimeTypes.return_value = "application/pdf"
    mock_desktop.getExec.side_effect = [
        "/usr/bin/madeup-evince",
        "/usr/local/bin/madeup-mupdf",
        "/usr/local/bin/madeup-libredraw",
    ]
    mock_desktop.getName.side_effect = [
        "Evince",
        "MuPDF",
        "LibreOffice",
    ]

    with (
        mock.patch(
            "subprocess.check_output",
            side_effect=subprocess.CalledProcessError(1, "Oh no, xdg-mime error!)"),
        ) as mock_default_mime_hander,
        mock.patch(
            "os.listdir",
            side_effect=[
                ["org.gnome.Evince.desktop"],
                ["org.pwmt.zathura-pdf-mupdf.desktop"],
                ["libreoffice-draw.desktop"],
            ],
        ) as mock_list,
        mock.patch("dangerzone.gui.logic.DesktopEntry", return_value=mock_desktop),
    ):
        dz = DangerzoneGui(mock_app, dummy)

        mock_default_mime_hander.assert_called_once_with(
            ["xdg-mime", "query", "default", "application/pdf"]
        )
        mock_list.assert_called()
        assert len(dz.pdf_viewers) == 3
        assert dz.pdf_viewers.popitem(last=False)[0] == "Evince"


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux-only test")
def test_malformed_desktop_entry_is_catched() -> None:
    """
    Given a failure to read a desktop entry,
    ensure that the exception is not thrown to the end-user.
    """
    mock_app = mock.MagicMock()
    dummy = mock.MagicMock()

    with (
        mock.patch("dangerzone.gui.logic.DesktopEntry") as mock_desktop,
        mock.patch(
            "os.listdir",
            side_effect=[
                ["malformed.desktop", "another.desktop"],
                [],
                [],
            ],
        ),
    ):
        mock_desktop.side_effect = ParsingError("Oh noes!", "malformed.desktop")
        DangerzoneGui(mock_app, dummy)
        mock_desktop.assert_called()
