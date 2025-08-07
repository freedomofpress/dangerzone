import typing
from typing import Optional

if typing.TYPE_CHECKING:
    from PySide2.QtCore import Qt
    from PySide2.QtGui import QTextCursor
    from PySide2.QtWidgets import QTextEdit
else:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QTextCursor
        from PySide6.QtWidgets import QTextEdit
    except ImportError:
        from PySide2.QtCore import Qt
        from PySide2.QtGui import QTextCursor
        from PySide2.QtWidgets import QTextEdit


class TracebackWidget(QTextEdit):
    """Reusable component to present tracebacks to the user.

    By default, the widget is initialized but does not appear. You need to call
    `.process_output(msg)` on it so the traceback is displayed.
    """

    def __init__(self) -> None:
        super(TracebackWidget, self).__init__()
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
