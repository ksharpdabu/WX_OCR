import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton
from wxocr.app import MainWindow
from wxocr.capture import CaptureOverlay
from wxocr.ocr import OCRWorker

app = QApplication.instance() or QApplication([])


@pytest.mark.parametrize('completion', ['button', 'enter'])
@pytest.mark.parametrize('initially_visible', [False, True])
def test_copy_from_capture_keeps_main_window_hidden(monkeypatch, completion, initially_visible):
    monkeypatch.setattr(OCRWorker, 'warmup', lambda self: None)
    monkeypatch.setattr(MainWindow, 'apply_hotkeys', lambda *args, **kwargs: None)
    window = MainWindow()
    image = QImage(300, 200, QImage.Format.Format_RGB32)
    image.fill(QColor('#3989ff'))
    overlay = CaptureOverlay(app.primaryScreen(), QPixmap.fromImage(image))
    overlay.resize(300, 200)
    overlay.selection = QRect(20, 20, 100, 80)
    overlay.selected.connect(window.captured)
    try:
        if initially_visible:
            window.show()
        window.was_visible = window.isVisible()
        window.capturing = True
        window.hide()  # capture() hides it before the overlay is displayed.
        overlay.show()
        if completion == 'button':
            button = next(b for b in overlay.toolbar.findChildren(QPushButton)
                          if b.text() == '复制 Enter')
            button.click()
        else:
            QTest.keyClick(overlay, Qt.Key.Key_Return)
        app.processEvents()
        assert not window.isVisible()
        assert not overlay.isVisible()
        assert not window.capturing
        assert app.clipboard().image().size() == window.image.size()
        assert app.clipboard().image().pixelColor(10, 10) == QColor('#3989ff')
    finally:
        overlay.close()
        window.shutdown()
        window.hide()


def test_ocr_capture_still_opens_result_window(monkeypatch):
    monkeypatch.setattr(OCRWorker, 'warmup', lambda self: None)
    monkeypatch.setattr(MainWindow, 'apply_hotkeys', lambda *args, **kwargs: None)
    recognized = []
    monkeypatch.setattr(MainWindow, 'recognize', lambda self: recognized.append(True))
    window = MainWindow()
    pixmap = QPixmap(100, 80)
    pixmap.fill(QColor('white'))
    try:
        window.captured(pixmap, 'ocr')
        assert window.isVisible()
        assert recognized == [True]
    finally:
        window.shutdown()
        window.hide()
