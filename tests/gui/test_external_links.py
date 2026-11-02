from pytestqt.qtbot import QtBot

from dangerzone.gui.logic import DangerzoneGui
from dangerzone.gui.main_window import WSLErrorWidget


def test_wsl_links_explain_external_browser(qtbot: QtBot) -> None:
    widget = WSLErrorWidget()
    qtbot.addWidget(widget)
    assert widget.explanation.text().count("(opens in browser)") == 3
    assert "↗" not in widget.explanation.text()


def test_external_label_preserves_markup_and_targets(qtbot: QtBot) -> None:
    from dangerzone.gui.widgets import ExternalLinkLabel

    label = ExternalLinkLabel()
    qtbot.addWidget(label)
    text = '<p>Read <a href="https://example.org/?a=1&amp;b=2"><b>our docs</b></a> &amp; <a href="http://example.org/">help</a>.</p>'
    label.setText(text)
    assert label.openExternalLinks()
    assert label.text() == text.replace("</a>", " (opens in browser)</a>")
    label.setText(label.text())
    assert label.text().count("(opens in browser)") == 2


def test_external_label_leaves_plain_text_and_local_links_alone(qtbot: QtBot) -> None:
    from dangerzone.gui.widgets import ExternalLinkLabel

    label = ExternalLinkLabel()
    qtbot.addWidget(label)
    for text in [
        "No links here",
        '<a href="#details">Details</a>',
        '<a href="file:///tmp/report.pdf">Report</a>',
    ]:
        label.setText(text)
        assert label.text() == text


def test_dialog_links_use_external_labels(
    qtbot: QtBot, dangerzone_gui: DangerzoneGui
) -> None:
    from dangerzone.gui.log_window import LogWindow
    from dangerzone.gui.logic import Alert, UpdateDialog
    from dangerzone.gui.main_window import StartupErrorWidget
    from dangerzone.gui.widgets import ExternalLinkLabel

    link = '<a href="https://example.org/">Help</a>'
    alert = Alert(dangerzone_gui, message=link)
    update = UpdateDialog(
        dangerzone_gui, title="Test", intro_msg=link, epilogue_msg=link
    )
    logs = LogWindow()
    logs.label.setText(link)
    startup = StartupErrorWidget()
    startup.handle_error("Test failure")
    for widget, count in [(alert, 1), (update, 2), (logs, 1), (startup, 1)]:
        qtbot.addWidget(widget)
        labels = widget.findChildren(ExternalLinkLabel)
        assert (
            sum(label.text().count("(opens in browser)") for label in labels) == count
        )


def test_update_prompt_uses_only_the_explicit_browser_indicator(qtbot: QtBot) -> None:
    from dangerzone.gui.updater import MSG_CONFIRM_UPDATE_CHECKS
    from dangerzone.gui.widgets import ExternalLinkLabel

    label = ExternalLinkLabel()
    qtbot.addWidget(label)
    label.setText(MSG_CONFIRM_UPDATE_CHECKS)
    assert label.text().count("(opens in browser)") == 1
    assert "↗" not in label.text()
