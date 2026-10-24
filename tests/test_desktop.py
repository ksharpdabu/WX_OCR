import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QRect
from PySide6.QtGui import QImage, QPixmap, QColor, QPainter, QFont
from PySide6.QtWidgets import QApplication
from wxocr.capture import CaptureOverlay
from wxocr.ocr import OCRWorker

app = QApplication.instance() or QApplication([])


def test_hidpi_crop_and_cancel():
    image = QPixmap(800, 600)
    image.fill(QColor("red"))
    image.setDevicePixelRatio(2)
    overlay = CaptureOverlay(app.primaryScreen(), image)
    overlay.resize(400, 300)
    overlay.selection = QRect(50, 30, 100, 80)
    results = []
    overlay.selected.connect(lambda p, a: results.append((p, a)))
    overlay.complete("copy")
    assert results[0][0].size().width() == 200
    assert results[0][0].size().height() == 160
    assert results[0][1] == "copy"
    cancelled = []
    overlay.cancelled.connect(lambda: cancelled.append(True))
    overlay.complete("cancel")
    assert cancelled == [True]


def test_real_ocr():
    image = QImage(700, 140, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setPen(QColor("black"))
    painter.setFont(QFont("DejaVu Sans", 40))
    painter.drawText(25, 90, "HELLO OCR 123")
    painter.end()
    worker = OCRWorker()
    results, errors = [], []
    worker.finished.connect(results.append)
    worker.failed.connect(errors.append)
    worker.recognize(image)
    assert not errors, errors
    assert "HELLO" in results[0].upper()
    assert "123" in results[0]
