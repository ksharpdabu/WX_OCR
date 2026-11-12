import os
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from wxocr.app import MainWindow


@pytest.mark.parametrize("visible", [False, True])
@pytest.mark.parametrize("action", ["copy", "save", "cancel", "ocr"])
def test_hotkey_capture_keeps_main_window_hidden(monkeypatch, visible, action):
    window = SimpleNamespace(
        busy=False, capturing=False, isVisible=lambda: visible,
        hide=Mock(), start_capture=Mock(), reveal=Mock(),
        set_image=Mock(), copy_image=Mock(), save_image=Mock(), recognize=Mock(),
    )
    window.capture = lambda *args, **kwargs: MainWindow.capture(window, *args, **kwargs)
    monkeypatch.setattr("wxocr.app.QTimer.singleShot", lambda delay, callback: callback())

    MainWindow.capture_from_hotkey(window)
    window.hide.assert_called_once()
    window.start_capture.assert_called_once_with(False)
    assert window.capturing

    if action == "cancel":
        MainWindow.capture_cancelled(window)
    else:
        image = object()
        MainWindow.captured(window, image, action)
        window.set_image.assert_called_once_with(image)
        {"copy": window.copy_image, "save": window.save_image,
         "ocr": window.recognize}[action].assert_called_once()
    assert not window.capturing
    assert window.reveal.call_count == (1 if action == "ocr" else 0)


def test_window_capture_restores_visible_window(monkeypatch):
    window = SimpleNamespace(
        busy=False, capturing=False, isVisible=lambda: True,
        hide=Mock(), start_capture=Mock(), reveal=Mock(),
        set_image=Mock(), copy_image=Mock(),
    )
    monkeypatch.setattr("wxocr.app.QTimer.singleShot", lambda delay, callback: callback())
    MainWindow.capture(window)
    MainWindow.captured(window, object(), "copy")
    window.reveal.assert_called_once()
