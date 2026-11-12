"""Small native EXE checks for annotation pixels, coordinates and input routing."""
from pathlib import Path
import sys

from PySide6.QtCore import QPoint, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPixmap
from PySide6.QtTest import QTest

from .annotations import Annotation, AnnotationDocument
from .capture import CaptureOverlay


def verify_annotations(app):
    # The Windows offscreen plugin has no automatic system font discovery.
    # Explicitly load a system font for the text-rasterization check.
    if sys.platform == 'win32':
        font_path = Path('C:/Windows/Fonts/arial.ttf')
        if font_path.is_file():
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                app.setFont(QFont(families[0]))
    image = QImage(400, 320, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor('white'))
    for kind in ('pen', 'arrow', 'rect', 'text'):
        document = AnnotationDocument(image, QSizeF(200, 160))
        original = document.render()
        document.commit(Annotation(kind, ((20, 20), (100, 80)), text='NOTE'))
        if document.render() == original:
            raise RuntimeError(f'{kind} produced no annotation pixels')
        document.undo()
        if document.render() != original:
            raise RuntimeError(f'{kind} undo did not restore the original')
    pattern = QImage(200, 160, QImage.Format.Format_RGB32)
    for x in range(pattern.width()):
        for y in range(pattern.height()):
            pattern.setPixelColor(x, y, QColor('white' if x % 2 else 'black'))
    document = AnnotationDocument(pattern, QSizeF(200, 160))
    document.commit(Annotation('mosaic', ((30, 60), (150, 60)), width=8))
    if document.render().pixelColor(80, 60) == pattern.pixelColor(80, 60):
        raise RuntimeError('Mosaic did not alter the painted pixels')
    if document.render().pixelColor(80, 10) != pattern.pixelColor(80, 10):
        raise RuntimeError('Mosaic altered pixels outside the painted region')
    snapshot = QPixmap.fromImage(image)
    snapshot.setDevicePixelRatio(2)
    for action in ('copy', 'save', 'ocr'):
        overlay = CaptureOverlay(app.primaryScreen(), snapshot)
        overlay.resize(200, 160)
        overlay.show()
        exported = []
        overlay.selected.connect(lambda pixmap, chosen: exported.append((pixmap.toImage(), chosen)))
        try:
            QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
            QTest.mouseMove(overlay, QPoint(160, 110))
            QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=QPoint(160, 110))
            overlay.toolbar.hide()
            overlay.choose_tool('pen')
            QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=QPoint(30, 30))
            QTest.mouseMove(overlay, QPoint(130, 30))
            QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=QPoint(130, 30))
            overlay.choose_tool('text')
            QTest.mouseClick(overlay, Qt.MouseButton.LeftButton, pos=QPoint(30, 60))
            overlay.text_editor.setText('NOTE')
            QTest.keyClick(overlay.text_editor, Qt.Key.Key_Return)
            if overlay.closed or len(overlay.document.actions) != 2:
                raise RuntimeError('Text Enter prematurely completed the screenshot')
            overlay.complete(action)
            output, chosen = exported[0]
            if chosen != action or output.width() != overlay.selection.width()*2:
                raise RuntimeError('Wrong annotation export action or HiDPI dimensions')
            if output.pixelColor(100, 40) != QColor('#ff4d4f'):
                raise RuntimeError('Annotation position or flattened export is incorrect')
        finally:
            overlay.close()
    return {'tools': ['pen', 'arrow', 'rect', 'mosaic', 'text'],
            'hidpi_scale': 2, 'flattened_actions': ['copy', 'save', 'ocr'], 'undo': True}
