"""Serial, persistent local inference; no image leaves this device."""
import os
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QImage


def create_engine():
    from rapidocr_onnxruntime import RapidOCR
    # Automatic ORT thread pools can oversubscribe the CPU across three sessions.
    # Keep the same detector/recognizer weights, but avoid enlarging every crop
    # to a minimum height of 736 pixels in the normal screenshot workflow.
    return RapidOCR(intra_op_num_threads=max(1, min(2, os.cpu_count() or 1)),
                    inter_op_num_threads=1, det_limit_type="max")


def to_bgr(image):
    if image.isNull():
        raise ValueError("图片为空")
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    pixels = np.frombuffer(rgba.bits(), dtype=np.uint8).reshape(
        rgba.height(), rgba.bytesPerLine())[:, :rgba.width() * 4]
    return pixels.reshape(rgba.height(), rgba.width(), 4)[:, :, :3][:, :, ::-1].copy()


class OCRWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)
    prepared = Signal()
    preparation_failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.engine = None

    def ensure_engine(self):
        if self.engine is None:
            self.engine = create_engine()

    @Slot()
    def warmup(self):
        try:
            self.ensure_engine()
            sample = QImage(str(Path(__file__).parent / "assets" / "ocr-sample.png"))
            self.engine(to_bgr(sample))
            self.prepared.emit()
        except Exception as exc:
            self.preparation_failed.emit(f"预热失败，识别时将重试：{exc}")

    @Slot(QImage, bool)
    def recognize(self, image, precise=False):
        try:
            self.ensure_engine()
            # RapidOCR 1.4.4 recreates its preprocessor on each call. Switching
            # this setting reuses all model sessions, with no second model load.
            self.engine.text_det.limit_type = "min" if precise else "max"
            result, _ = self.engine(to_bgr(image))
            self.finished.emit("\n".join(line[1] for line in (result or [])))
        except Exception as exc:
            self.failed.emit(f"文字识别失败：{exc}")
