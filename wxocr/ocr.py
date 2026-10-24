"""OCR runs serially in a worker thread; images never leave this device."""
import numpy as np
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QImage


class OCRWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.engine = None

    @Slot(QImage)
    def recognize(self, image):
        try:
            if self.engine is None:
                from rapidocr_onnxruntime import RapidOCR
                self.engine = RapidOCR()
            rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
            pixels = np.frombuffer(rgba.bits(), dtype=np.uint8).reshape(
                rgba.height(), rgba.bytesPerLine())[:, :rgba.width() * 4]
            bgr = pixels.reshape(rgba.height(), rgba.width(), 4)[:, :, :3][:, :, ::-1].copy()
            result, _ = self.engine(bgr)
            self.finished.emit("\n".join(line[1] for line in (result or [])))
        except Exception as exc:
            self.failed.emit(f"文字识别失败：{exc}")
