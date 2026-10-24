"""Compare old and new inference on identical fixed images on one machine."""
import json
from pathlib import Path
from statistics import median
from time import perf_counter


def run(report_path):
    import cv2
    from rapidocr_onnxruntime import RapidOCR
    from PySide6.QtGui import QImage
    from .ocr import create_engine, to_bgr
    sample = to_bgr(QImage(str(Path(__file__).parent / "assets" / "ocr-sample.png")))
    images = {"two_lines": sample, "small_text": cv2.resize(sample, (400, 120))}
    report = {}
    # Same model weights, same inputs and orientation correction in both modes.
    for name, factory in [("previous", RapidOCR), ("optimized", create_engine)]:
        engine = factory()
        cases = {}
        for case_name, image in images.items():
            engine(image)  # Warm both implementations before comparing.
            times = []
            for _ in range(3):
                started = perf_counter()
                result, _ = engine(image)
                times.append(perf_counter() - started)
            text = "\n".join(row[1] for row in (result or []))
            if "HELLO" not in text.upper() or "微信" not in text:
                raise RuntimeError(f"{name}/{case_name} lost expected text: {text}")
            cases[case_name] = {"median_seconds": median(times), "samples_seconds": times, "text": text}
        report[name] = cases
        del engine
    report["speedup"] = {case: report["previous"][case]["median_seconds"] / report["optimized"][case]["median_seconds"] for case in images}
    Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0
