from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton


class CaptureOverlay(QWidget):
    selected = Signal(object, str)
    cancelled = Signal()

    def __init__(self, screen, pixmap, auto_ocr=False):
        super().__init__()
        self.snapshot = pixmap
        self.auto_ocr = auto_ocr
        self.origin = None
        self.selection = QRect()
        self.dragging = False
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setGeometry(screen.geometry())
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.toolbar = QWidget(self)
        self.toolbar.setStyleSheet("QWidget {background:#202b28;color:white;border-radius:6px;} QPushButton {padding:8px;border:0;} QPushButton:hover {background:#168b60;}")
        layout = QHBoxLayout(self.toolbar)
        for label, action in [("复制 Enter", "copy"), ("保存", "save"), ("识别文字", "ocr"), ("取消 Esc", "cancel")]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, a=action: self.complete(a))
            layout.addWidget(button)
        self.toolbar.hide()

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawPixmap(self.rect(), self.snapshot)
        p.fillRect(self.rect(), QColor(0, 0, 0, 105))
        if not self.selection.isEmpty():
            p.save()
            p.setClipRect(self.selection)
            p.drawPixmap(self.rect(), self.snapshot)
            p.restore()
            p.setPen(QPen(QColor("#07c160"), 2))
            p.drawRect(self.selection)
            p.setPen(Qt.GlobalColor.white)
            p.drawText(self.selection.topLeft() + QPoint(3, -8), f"{self.selection.width()} × {self.selection.height()}")
        else:
            p.setPen(Qt.GlobalColor.white)
            p.drawText(QPoint(30, 40), "拖动鼠标选择截图区域 · Esc 取消 · 当前鼠标所在屏幕")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.complete("cancel")
        elif event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.position().toPoint()
            self.dragging = True
            self.selection = QRect()
            self.toolbar.hide()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.selection = QRect(self.origin, event.position().toPoint()).normalized().intersected(self.rect())
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or not self.dragging:
            return
        self.dragging = False
        if self.selection.width() < 3 or self.selection.height() < 3:
            self.selection = QRect()
            self.update()
            return
        if self.auto_ocr:
            self.complete("ocr")
            return
        self.toolbar.adjustSize()
        self.toolbar.move(max(0, min(self.selection.right() - self.toolbar.width(), self.width() - self.toolbar.width())),
                          max(0, min(self.selection.bottom() + 8, self.height() - self.toolbar.height())))
        self.toolbar.show()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.complete("cancel")
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.complete("copy")

    def complete(self, action):
        if action == "cancel":
            self.hide()
            self.cancelled.emit()
        elif not self.selection.isEmpty():
            # Map logical overlay coordinates to physical source pixels on HiDPI displays.
            sx = self.snapshot.width() / self.width()
            sy = self.snapshot.height() / self.height()
            r = self.selection
            crop = self.snapshot.copy(QRect(round(r.x()*sx), round(r.y()*sy), round(r.width()*sx), round(r.height()*sy)))
            self.hide()
            self.selected.emit(crop, action)
