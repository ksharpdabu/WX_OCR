import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPoint, QRect, QSizeF, Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from wxocr.annotations import Annotation, AnnotationDocument
from wxocr.capture import CaptureOverlay

app = QApplication.instance() or QApplication([])


def white_image(width=200, height=160):
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor('white'))
    return image


def overlay_for_test(dpr=1):
    pixmap = QPixmap.fromImage(white_image(400*dpr, 300*dpr))
    pixmap.setDevicePixelRatio(dpr)
    overlay = CaptureOverlay(app.primaryScreen(), pixmap)
    overlay.resize(400, 300)
    overlay.show()
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
    QTest.mouseMove(overlay, QPoint(220, 180))
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=QPoint(220, 180))
    app.processEvents()
    return overlay


def stroke(overlay, tool, start, end):
    overlay.choose_tool(tool)
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(overlay, end)
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=end)


@pytest.mark.parametrize('kind', ['pen', 'arrow', 'rect', 'text'])
def test_annotations_change_pixels_and_undo_restores_original(kind):
    document = AnnotationDocument(white_image(), QSizeF(200, 160))
    original = document.render()
    document.commit(Annotation(kind, ((20, 20), (100, 80)), text='HELLO'))
    assert document.render() != original
    document.undo()
    assert document.render() == original


def test_mosaic_is_flattened_and_only_changes_painted_region(tmp_path):
    image = white_image()
    # Fine alternating stripes make a clear privacy masking regression fixture.
    for x in range(image.width()):
        for y in range(image.height()):
            image.setPixelColor(x, y, QColor('black' if x % 2 else 'white'))
    document = AnnotationDocument(image, QSizeF(200, 160))
    original = document.render()
    document.commit(Annotation('mosaic', ((40, 60), (140, 60)), width=8))
    output = document.render()
    assert output.pixelColor(81, 60) != original.pixelColor(81, 60)
    assert output.pixelColor(81, 10) == original.pixelColor(81, 10)
    path = tmp_path / 'redacted.png'
    assert output.save(str(path))
    assert QImage(str(path)).pixelColor(81, 60) == output.pixelColor(81, 60)
    document.undo()
    assert document.render() == original


def test_hidpi_stroke_preview_export_and_shortcut_undo():
    overlay = overlay_for_test(dpr=2)
    try:
        overlay.toolbar.hide()  # Keep the event fixture clear on small CI screens.
        stroke(overlay, 'pen', QPoint(50, 50), QPoint(140, 50))
        # Local (60, 30) maps to physical pixel (120, 60), with crop offset removed.
        assert overlay.document.render().pixelColor(120, 60) == QColor('#ff4d4f')
        QTest.keyClick(overlay, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        assert overlay.document.render().pixelColor(120, 60) == QColor('white')
        stroke(overlay, 'pen', QPoint(50, 50), QPoint(140, 50))
        result = []
        overlay.selected.connect(lambda pixmap, action: result.append((pixmap.toImage(), action)))
        overlay.complete('copy')
        assert result[0][0].width() == overlay.selection.width()*2
        assert result[0][0].height() == overlay.selection.height()*2
        assert result[0][0].pixelColor(120, 60) == QColor('#ff4d4f')
        overlay.complete('copy')
        assert len(result) == 1
    finally:
        overlay.close()


@pytest.mark.parametrize('action', ['copy', 'save', 'ocr'])
def test_all_completion_actions_receive_annotated_image(action):
    overlay = overlay_for_test()
    try:
        overlay.toolbar.hide()
        stroke(overlay, 'rect', QPoint(50, 50), QPoint(130, 110))
        expected = overlay.document.render()
        assert expected.pixelColor(30, 40) == QColor('#ff4d4f')
        result = []
        overlay.selected.connect(lambda pixmap, chosen: result.append((pixmap.toImage(), chosen)))
        overlay.complete(action)
        assert result[0][0].convertToFormat(expected.format()) == expected
        assert result[0][1] == action
    finally:
        overlay.close()


def test_inline_text_enter_commits_escape_discards_and_export_commits():
    overlay = overlay_for_test()
    try:
        overlay.toolbar.hide()
        overlay.choose_tool('text')
        QTest.mouseClick(overlay, Qt.MouseButton.LeftButton, pos=QPoint(40, 40))
        overlay.text_editor.setText('说明 HELLO')
        QTest.keyClick(overlay.text_editor, Qt.Key.Key_Return)
        assert len(overlay.document.actions) == 1
        assert overlay.document.actions[0].text == '说明 HELLO'
        assert not overlay.closed  # Enter inside the editor confirms text only.
        QTest.mouseClick(overlay, Qt.MouseButton.LeftButton, pos=QPoint(40, 80))
        overlay.text_editor.setText('discard me')
        QTest.keyClick(overlay.text_editor, Qt.Key.Key_Escape)
        assert len(overlay.document.actions) == 1
        assert not overlay.closed
        QTest.mouseClick(overlay, Qt.MouseButton.LeftButton, pos=QPoint(40, 100))
        overlay.text_editor.setText('commit on export')
        overlay.complete('save')
        assert len(overlay.document.actions) == 2
    finally:
        overlay.close()


def test_reselect_clears_annotations_and_cancel_never_exports():
    overlay = overlay_for_test()
    try:
        overlay.toolbar.hide()
        stroke(overlay, 'pen', QPoint(50, 50), QPoint(140, 50))
        overlay.reset_selection()
        assert overlay.document is None and overlay.selection.isEmpty()
        assert not overlay.toolbar.isVisible()
        exported, cancelled = [], []
        overlay.selected.connect(lambda *args: exported.append(args))
        overlay.cancelled.connect(lambda: cancelled.append(True))
        QTest.keyClick(overlay, Qt.Key.Key_Escape)
        assert not exported and cancelled == [True]
    finally:
        overlay.close()


def test_auto_ocr_selection_still_completes_immediately():
    overlay = CaptureOverlay(app.primaryScreen(), QPixmap.fromImage(white_image()), auto_ocr=True)
    overlay.resize(200, 160)
    result = []
    overlay.selected.connect(lambda pixmap, action: result.append(action))
    overlay.show()
    try:
        QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
        QTest.mouseMove(overlay, QPoint(160, 110))
        QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=QPoint(160, 110))
        assert result == ['ocr']
    finally:
        overlay.close()


def test_undo_mosaic_preserves_previous_markup():
    document = AnnotationDocument(white_image(), QSizeF(200, 160))
    document.commit(Annotation('pen', ((20, 40), (150, 40)), width=4))
    marked = document.render()
    document.commit(Annotation('mosaic', ((30, 40), (140, 40)), width=8))
    assert document.render() != marked
    document.undo()
    assert document.render() == marked


def test_color_and_width_options_affect_exported_pixels():
    overlay = overlay_for_test(dpr=2)
    try:
        overlay.toolbar.hide()
        overlay.choose_color('#3989ff')
        overlay.width_box.setCurrentIndex(3)  # 16 logical pixels
        stroke(overlay, 'pen', QPoint(50, 50), QPoint(150, 50))
        image = overlay.document.render()
        assert image.pixelColor(100, 70) == QColor('#3989ff')
        assert image.pixelColor(100, 82) == QColor('white')
    finally:
        overlay.close()


def test_chinese_input_composition_does_not_finish_capture():
    from PySide6.QtGui import QInputMethodEvent
    overlay = overlay_for_test()
    try:
        overlay.toolbar.hide()
        overlay.choose_tool('text')
        QTest.mouseClick(overlay, Qt.MouseButton.LeftButton, pos=QPoint(40, 40))
        QApplication.sendEvent(overlay.text_editor, QInputMethodEvent('zhong', []))
        assert overlay.text_composing
        QTest.keyClick(overlay.text_editor, Qt.Key.Key_Return)
        assert not overlay.closed
        event = QInputMethodEvent()
        event.setCommitString('中文标注')
        QApplication.sendEvent(overlay.text_editor, event)
        QTest.keyClick(overlay.text_editor, Qt.Key.Key_Return)
        assert overlay.document.actions[-1].text == '中文标注'
        assert not overlay.closed
    finally:
        overlay.close()


def test_undo_cancels_unfinished_stroke_without_removing_previous_mark():
    overlay = overlay_for_test()
    try:
        overlay.toolbar.hide()
        stroke(overlay, 'pen', QPoint(50, 50), QPoint(140, 50))
        previous = overlay.document.render()
        QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=QPoint(50, 90))
        QTest.mouseMove(overlay, QPoint(140, 90))
        QTest.keyClick(overlay, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=QPoint(140, 90))
        assert overlay.document.render() == previous
        assert len(overlay.document.actions) == 1
    finally:
        overlay.close()


def test_closing_overlay_cancels_and_does_not_export():
    overlay = overlay_for_test()
    cancelled, exported = [], []
    overlay.cancelled.connect(lambda: cancelled.append(True))
    overlay.selected.connect(lambda *args: exported.append(args))
    overlay.close()
    assert cancelled == [True]
    assert not exported
