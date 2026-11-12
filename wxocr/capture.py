from PySide6.QtCore import QPoint, QPointF, QRect, QSizeF, Qt, QEvent, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
                              QButtonGroup, QComboBox, QLabel, QLineEdit)

from .annotations import Annotation, AnnotationDocument


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
        self.document = None
        self.pending = None
        self.stroke_points = []
        self.tool = None
        self.color = '#ff4d4f'
        self.closed = False
        self.text_anchor = None
        self.text_style = None
        self.text_composing = False
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setGeometry(screen.geometry())
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self._build_toolbar()
        self.text_editor = QLineEdit(self)
        self.text_editor.setObjectName('annotation-text')
        self.text_editor.setPlaceholderText('输入文字，Enter 确认，Esc 取消')
        self.text_editor.installEventFilter(self)
        self.text_editor.hide()

    def _build_toolbar(self):
        self.toolbar = QWidget(self)
        self.toolbar.setObjectName('annotation-toolbar')
        self.toolbar.setStyleSheet('''
            QWidget {background:#202b28;color:white;border-radius:6px;}
            QPushButton {padding:7px;border:1px solid transparent;}
            QPushButton:hover, QPushButton:checked {background:#168b60;border-color:#70e1ac;}
            QPushButton:disabled {color:#708378;}
            QComboBox {padding:3px;border:1px solid #53675c;}
        ''')
        layout = QVBoxLayout(self.toolbar)
        layout.setSpacing(3)
        tools = QHBoxLayout()
        self.tool_group = QButtonGroup(self)
        self.tool_buttons = {}
        for label, tool in [('画笔', 'pen'), ('箭头', 'arrow'), ('矩形', 'rect'), ('马赛克', 'mosaic'), ('文字', 'text')]:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setObjectName('tool-' + tool)
            self.tool_group.addButton(button)
            button.clicked.connect(lambda checked=False, t=tool: self.choose_tool(t))
            self.tool_buttons[tool] = button
            tools.addWidget(button)
        self.undo_button = QPushButton('撤销 Ctrl+Z')
        self.undo_button.clicked.connect(self.undo)
        self.undo_button.setEnabled(False)
        tools.addWidget(self.undo_button)
        reset = QPushButton('重选')
        reset.clicked.connect(self.reset_selection)
        tools.addWidget(reset)
        layout.addLayout(tools)
        options = QHBoxLayout()
        self.color_buttons = []
        for color in ['#ff4d4f', '#ffdb4d', '#07c160', '#3989ff', '#ffffff', '#111111']:
            button = QPushButton()
            button.setFixedSize(22, 22)
            button.setToolTip(color)
            button.clicked.connect(lambda checked=False, c=color: self.choose_color(c))
            self.color_buttons.append((button, color))
            options.addWidget(button)
        self.choose_color(self.color)
        options.addWidget(QLabel('笔触'))
        self.width_box = QComboBox()
        for width in (2, 4, 8, 16):
            self.width_box.addItem(str(width), width)
        self.width_box.setCurrentIndex(1)
        options.addWidget(self.width_box)
        options.addWidget(QLabel('字号'))
        self.font_box = QComboBox()
        for size in (14, 20, 28, 36, 48):
            self.font_box.addItem(str(size), size)
        self.font_box.setCurrentIndex(1)
        options.addWidget(self.font_box)
        layout.addLayout(options)
        actions = QHBoxLayout()
        for label, action in [('复制 Enter', 'copy'), ('保存', 'save'), ('识别文字', 'ocr'), ('取消 Esc', 'cancel')]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, a=action: self.complete(a))
            actions.addWidget(button)
        layout.addLayout(actions)
        self.toolbar.hide()

    def choose_tool(self, tool):
        self.commit_text()
        self.tool = tool
        self.tool_buttons[tool].setChecked(True)
        self.setFocus()
        self.setCursor(Qt.CursorShape.IBeamCursor if tool == 'text' else Qt.CursorShape.CrossCursor)

    def choose_color(self, color):
        if hasattr(self, 'text_editor'):
            self.commit_text()
        self.color = color
        for button, value in self.color_buttons:
            border = '2px solid white' if value == color else '1px solid #58675e'
            button.setStyleSheet(f'background:{value};border:{border};border-radius:4px;padding:0;')

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawPixmap(self.rect(), self.snapshot)
        p.fillRect(self.rect(), QColor(0, 0, 0, 105))
        if not self.selection.isEmpty():
            if self.document:
                p.drawImage(self.selection, self.document.render(self.pending))
            else:
                p.save()
                p.setClipRect(self.selection)
                p.drawPixmap(self.rect(), self.snapshot)
                p.restore()
            p.setPen(QPen(QColor('#07c160'), 2))
            p.drawRect(self.selection)
            p.setPen(Qt.GlobalColor.white)
            p.drawText(self.selection.topLeft() + QPoint(3, -8), f'{self.selection.width()} × {self.selection.height()}')
        else:
            p.setPen(Qt.GlobalColor.white)
            p.drawText(QPoint(30, 40), '拖动选择区域 · 框选后可画笔、箭头、马赛克、添加文字 · Esc 取消')

    def _crop(self):
        sx = self.snapshot.width() / self.width()
        sy = self.snapshot.height() / self.height()
        r = self.selection
        return self.snapshot.copy(QRect(round(r.x()*sx), round(r.y()*sy), round(r.width()*sx), round(r.height()*sy)))

    def _ensure_document(self):
        if self.document is None:
            self.document = AnnotationDocument(self._crop().toImage(), QSizeF(self.selection.size()))

    def _local_point(self, position):
        point = position - QPointF(self.selection.topLeft())
        return (max(0.0, min(point.x(), self.selection.width()-1.0)),
                max(0.0, min(point.y(), self.selection.height()-1.0)))

    def _annotation(self):
        return Annotation(self.tool, tuple(self.stroke_points), self.color, self.width_box.currentData())

    def mousePressEvent(self, event):
        if self.closed:
            return
        if event.button() == Qt.MouseButton.RightButton:
            self.complete('cancel')
        elif event.button() == Qt.MouseButton.LeftButton:
            self.commit_text()
            if self.document is None:
                self.origin = event.position().toPoint()
                self.dragging = True
                self.selection = QRect()
                self.toolbar.hide()
            elif self.tool and self.selection.contains(event.position().toPoint()):
                point = self._local_point(event.position())
                if self.tool == 'text':
                    self.start_text(point)
                else:
                    self.stroke_points = [point]
                    self.pending = self._annotation()
                    self.update()

    def mouseMoveEvent(self, event):
        if self.closed:
            return
        if self.dragging:
            self.selection = QRect(self.origin, event.position().toPoint()).normalized().intersected(self.rect())
            self.update()
        elif self.pending:
            point = self._local_point(event.position())
            if self.tool in ('rect', 'arrow'):
                self.stroke_points = [self.stroke_points[0], point]
            elif point != self.stroke_points[-1]:
                self.stroke_points.append(point)
            self.pending = self._annotation()
            self.update()

    def mouseReleaseEvent(self, event):
        if self.closed or event.button() != Qt.MouseButton.LeftButton:
            return
        if self.pending:
            self.mouseMoveEvent(event)
            self.document.commit(self.pending)
            self.pending = None
            self.stroke_points = []
            self.undo_button.setEnabled(bool(self.document.actions))
            self.update()
            return
        if not self.dragging:
            return
        self.selection = QRect(self.origin, event.position().toPoint()).normalized().intersected(self.rect())
        self.dragging = False
        if self.selection.width() < 3 or self.selection.height() < 3:
            self.selection = QRect()
            self.update()
            return
        self._ensure_document()
        if self.auto_ocr:
            self.complete('ocr')
            return
        self._position_toolbar()
        self.toolbar.show()
        self.setFocus()
        self.update()

    def _position_toolbar(self):
        self.toolbar.adjustSize()
        x = max(0, min(self.selection.right()-self.toolbar.width(), self.width()-self.toolbar.width()))
        y = self.selection.bottom() + 8
        if y + self.toolbar.height() > self.height():
            y = self.selection.top() - self.toolbar.height() - 8
        self.toolbar.move(x, max(0, min(y, self.height()-self.toolbar.height())))

    def start_text(self, point):
        point = (min(point[0], max(0, self.selection.width()-self.font_box.currentData())),
                 min(point[1], max(0, self.selection.height()-self.font_box.currentData()-4)))
        self.text_anchor = point
        self.text_composing = False
        self.text_style = (self.color, self.font_box.currentData())
        font = QFont()
        font.setPixelSize(self.text_style[1])
        self.text_editor.setFont(font)
        self.text_editor.setStyleSheet(f'color:{self.color};background:white;border:1px solid #07c160;padding:3px;')
        self.text_editor.clear()
        width = min(300, self.width())
        x = min(self.selection.x()+round(point[0]), self.width()-width)
        y = min(self.selection.y()+round(point[1]), self.height()-self.text_editor.sizeHint().height())
        self.text_editor.setGeometry(max(0, x), max(0, y), width, self.text_editor.sizeHint().height())
        self.text_editor.show()
        self.text_editor.raise_()
        self.text_editor.setFocus()

    def commit_text(self):
        if not hasattr(self, 'text_editor') or not self.text_editor.isVisible():
            return
        text = self.text_editor.text()
        self.text_editor.hide()
        if text.strip() and self.document:
            self.document.commit(Annotation('text', (self.text_anchor,), self.text_style[0],
                                            text=text, font_size=self.text_style[1]))
            self.undo_button.setEnabled(True)
            self.update()
        self.setFocus()

    def eventFilter(self, obj, event):
        if obj is self.text_editor:
            if event.type() == QEvent.Type.InputMethod:
                self.text_composing = bool(event.preeditString())
            elif event.type() == QEvent.Type.KeyPress:
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not self.text_composing:
                    self.commit_text()
                    return True
                if event.key() == Qt.Key.Key_Escape and not self.text_composing:
                    self.text_editor.hide()
                    self.setFocus()
                    return True
        return super().eventFilter(obj, event)

    def undo(self):
        self.commit_text()
        if self.pending:
            self.pending = None
            self.stroke_points = []
            self.update()
            return
        if self.document:
            self.document.undo()
            self.undo_button.setEnabled(bool(self.document.actions))
            self.update()
        self.setFocus()

    def reset_selection(self):
        self.text_editor.hide()
        self.document = None
        self.pending = None
        self.stroke_points = []
        self.selection = QRect()
        self.dragging = False
        self.tool = None
        self.tool_group.setExclusive(False)
        for button in self.tool_buttons.values():
            button.setChecked(False)
        self.tool_group.setExclusive(True)
        self.undo_button.setEnabled(False)
        self.toolbar.hide()
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocus()
        self.update()

    def keyPressEvent(self, event):
        if self.text_editor.isVisible() and self.text_composing:
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.complete('cancel')
        elif event.key() == Qt.Key.Key_Z and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.undo()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.complete('copy')
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if not self.closed:
            self.complete('cancel')
        event.accept()

    def complete(self, action):
        if self.closed:
            return
        if action == 'cancel':
            self.closed = True
            self.hide()
            self.cancelled.emit()
        elif not self.selection.isEmpty():
            self.commit_text()
            self._ensure_document()
            if self.pending:
                self.document.commit(self.pending)
                self.pending = None
            crop = QPixmap.fromImage(self.document.render())
            self.closed = True
            self.hide()
            self.selected.emit(crop, action)
