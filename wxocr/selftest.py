"""Exercise Qt, bundled models and ONNX runtime inside the packaged executable."""
import json
import traceback
from pathlib import Path


def run(report_path):
    report = {"ok": False}
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QImage
        from .ocr import OCRWorker
        app = QApplication.instance() or QApplication([])
        image = QImage(str(Path(__file__).parent / 'assets' / 'ocr-sample.png'))
        if image.isNull():
            raise RuntimeError('Bundled OCR test image is missing')
        worker = OCRWorker()
        results, errors = [], []
        worker.finished.connect(results.append)
        worker.failed.connect(errors.append)
        worker.recognize(image)
        if errors:
            raise RuntimeError(errors[0])
        if not results or 'HELLO' not in results[0].upper() or '123' not in results[0] or '微信' not in results[0]:
            raise RuntimeError(f'OCR result mismatch: {results}')
        from .app import MainWindow
        window = MainWindow()
        try:
            window.show()
            app.processEvents()
            report.update(ok=True, ocr_text=results[0], window_created=True)
        finally:
            window.shutdown()
    except Exception:
        report['error'] = traceback.format_exc()
    Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if report['ok'] else 1
