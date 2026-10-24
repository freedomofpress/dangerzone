import typing
from html.parser import HTMLParser
from urllib.parse import urlsplit

if typing.TYPE_CHECKING:
    from PySide2 import QtWidgets
    from PySide2.QtCore import Qt
    from PySide2.QtGui import QTextCursor
else:
    try:
        from PySide6 import QtWidgets
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QTextCursor
    except ImportError:
        from PySide2 import QtWidgets
        from PySide2.QtCore import Qt
        from PySide2.QtGui import QTextCursor


class _ExternalLinkIndicators(HTMLParser):
    """Preserve rich text while labelling links that leave the application."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self.anchor_start: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.parts.append(self.get_starttag_text() or "")
        if tag == "a":
            href = dict(attrs).get("href") or ""
            if urlsplit(href).scheme.lower() in ("http", "https"):
                self.anchor_start = len(self.parts)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.anchor_start is not None:
            label = "".join(self.parts[self.anchor_start :])
            if "(opens in browser)" not in label:
                self.parts.append(" (opens in browser)")
            self.anchor_start = None
        self.parts.append(f"</{tag}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.parts.append(self.get_starttag_text() or "")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")


class ExternalLinkLabel(QtWidgets.QLabel):
    """A rich-text label whose web links explain where they will open."""

    def __init__(self) -> None:
        super().__init__()
        self.setOpenExternalLinks(True)

    def setText(self, text: str) -> None:
        parser = _ExternalLinkIndicators()
        parser.feed(text)
        parser.close()
        super().setText("".join(parser.parts))


class TracebackWidget(QtWidgets.QTextEdit):
    """Reusable component to present tracebacks to the user.

    By default, the widget is initialized but does not appear. You need to call
    `.process_output(msg)` on it so the traceback is displayed.
    """

    def __init__(self) -> None:
        super().__init__()
        # Error
        self.setReadOnly(True)
        self.setVisible(False)
        self.setProperty("style", "traceback")
        # Enable copying
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.current_output = ""

    def process_output(self, line: str) -> None:
        self.setVisible(True)
        self.current_output += line
        self.setText(self.current_output)
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)

    def copy_to_clipboard(self) -> None:
        QtWidgets.QApplication.clipboard().setText(self.toPlainText())
