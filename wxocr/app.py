import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter

from PySide6.QtCore import QSettings, QThread, QTimer, Signal, Qt
from PySide6.QtGui import QAction, QColor, QCursor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QLineEdit, QGroupBox, QFormLayout, QMessageBox,
    QFileDialog, QSystemTrayIcon, QMenu, QSplitter, QCheckBox,
)
from .capture import CaptureOverlay
from .hotkeys import normalize_hotkey, pynput_hotkey
from .ocr import OCRWorker
from . import startup, __version__


class MainWindow(QMainWindow):
    capture_requested = Signal(bool)
    ocr_requested = Signal(QImage, bool)
    hotkey_failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"青截 {__version__} · 截图与文字识别")
        self.resize(920, 680)
        self.settings = QSettings("WXOCR", "QingJie")
        self.listener = None
        self.overlay = None
        self.capturing = False
        self.busy = False
        self.image = QPixmap()
        self.thread = QThread(self)
        self.worker = OCRWorker()
        self.worker.moveToThread(self.thread)
        self.ocr_requested.connect(self.worker.recognize)
        self.worker.finished.connect(self.ocr_finished)
        self.worker.failed.connect(self.ocr_failed)
        self.thread.finished.connect(self.worker.deleteLater)
        self.capture_requested.connect(self.capture)
        self.hotkey_failed.connect(self.report_hotkey_error)
        self.build_ui()
        self.build_tray()
        self.apply_hotkeys(initial=True)
        if self.startup_read_error:
            self.status.setText(self.startup_read_error)
        self.worker.prepared.connect(lambda: self.engine_status.setText("OCR 已就绪 · 模型常驻内存"))
        self.worker.preparation_failed.connect(self.engine_status.setText)
        self.thread.started.connect(self.worker.warmup)
        self.thread.start()

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 24)
        title = QLabel("青截  /  随手截，轻松识")
        title.setStyleSheet("font-size:26px;font-weight:700;color:#174e3e")
        layout.addWidget(title)
        layout.addWidget(QLabel("框选屏幕 · 本地中英文 OCR · 自定义全局快捷键"))
        actions = QHBoxLayout()
        for label, callback in [("＋ 开始截图", lambda: self.capture(False)),
                                ("截图识字", lambda: self.capture(True)),
                                ("打开图片", self.open_image), ("复制图片", self.copy_image),
                                ("保存图片", self.save_image)]:
            b = QPushButton(label)
            b.clicked.connect(callback)
            actions.addWidget(b)
        layout.addLayout(actions)
        splitter = QSplitter()
        self.preview = QLabel("截图或打开一张图片\n\n框选后可复制、保存或识别文字")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(280, 240)
        self.preview.setStyleSheet("background:#edf3ef;border:1px solid #d9e5dd;border-radius:10px;color:#667e70")
        splitter.addWidget(self.preview)
        right = QWidget()
        r = QVBoxLayout(right)
        r.setContentsMargins(12, 0, 0, 0)
        r.addWidget(QLabel("识别结果 · 可直接编辑"))
        self.text = QTextEdit()
        self.text.setPlaceholderText("识别出的文字会显示在这里…")
        r.addWidget(self.text)
        self.precise = QCheckBox("精细识别（适合小字、密集文本，较慢）")
        self.precise.setChecked(self.settings.value("precise_ocr", False, type=bool))
        self.precise.toggled.connect(lambda checked: self.settings.setValue("precise_ocr", checked))
        r.addWidget(self.precise)
        buttons = QHBoxLayout()
        self.recognize_button = QPushButton("识别当前图片")
        self.recognize_button.clicked.connect(self.recognize)
        buttons.addWidget(self.recognize_button)
        copy = QPushButton("复制文字")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.text.toPlainText()))
        buttons.addWidget(copy)
        r.addLayout(buttons)
        splitter.addWidget(right)
        layout.addWidget(splitter, 1)
        group = QGroupBox("设置")
        form = QFormLayout(group)
        self.capture_key = QLineEdit(self.settings.value("capture_key", "ctrl+alt+a"))
        self.ocr_key = QLineEdit(self.settings.value("ocr_key", "ctrl+alt+o"))
        form.addRow("截图", self.capture_key)
        form.addRow("截图并识字", self.ocr_key)
        save = QPushButton("保存快捷键")
        save.clicked.connect(lambda: self.apply_hotkeys())
        form.addRow("例如 Ctrl+Alt+A / Cmd+Shift+A", save)
        self.autostart = QCheckBox("开机启动（登录 Windows 后常驻托盘）")
        self.autostart.setToolTip("立即生效，无需管理员权限。移动程序目录后，请取消再重新勾选。")
        self.startup_read_error = None
        if startup.SUPPORTED:
            try:
                self.autostart.setChecked(startup.is_enabled())
            except OSError as exc:
                self.autostart.setEnabled(False)
                self.startup_read_error = f"无法读取开机启动设置：{exc}"
                self.autostart.setToolTip(self.startup_read_error)
        else:
            self.autostart.setEnabled(False)
            self.autostart.setToolTip("开机启动设置目前仅支持 Windows")
        self.autostart.toggled.connect(self.set_autostart)
        form.addRow("启动", self.autostart)
        layout.addWidget(group)
        self.status = QLabel("就绪 · 图片与识别结果仅保存在本机")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.engine_status = QLabel("OCR 正在后台准备 · 准备后可快速识别")
        layout.addWidget(self.engine_status)
        self.setStyleSheet("QMainWindow {background:#fafcfb} QPushButton {background:#e3f4e9;color:#155c3d;border:1px solid #c3e4d0;border-radius:6px;padding:9px;} QPushButton:hover {background:#c8ead6} QLineEdit,QTextEdit {background:white;border:1px solid #d3dfd7;border-radius:5px;padding:7px;} QGroupBox {border:1px solid #d3dfd7;border-radius:7px;margin-top:12px;padding-top:14px;}")

    def set_autostart(self, enabled):
        try:
            startup.set_enabled(enabled)
        except OSError as exc:
            # Reflect the unchanged system setting when writing is rejected.
            self.autostart.blockSignals(True)
            self.autostart.setChecked(not enabled)
            self.autostart.blockSignals(False)
            self.status.setText(f"开机启动设置失败：{exc}")
            return
        self.status.setText("已开启开机启动，下次登录 Windows 后会常驻托盘" if enabled else "已关闭开机启动")

    def build_tray(self):
        icon = QPixmap(64, 64)
        icon.fill(QColor("#07a960"))
        p = QPainter(icon)
        p.setPen(QColor("white"))
        p.drawRect(15, 15, 34, 34)
        p.drawText(22, 39, "截")
        p.end()
        self.setWindowIcon(QIcon(icon))
        self.tray = QSystemTrayIcon(QIcon(icon), self)
        menu = QMenu(self)
        for label, callback in [("截图", lambda: self.capture(False)), ("截图识字", lambda: self.capture(True)),
                                ("打开主窗口", self.reveal), ("退出", QApplication.instance().quit)]:
            action = QAction(label, self)
            action.triggered.connect(callback)
            menu.addAction(action)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip("青截 · 截图与 OCR")
        self.tray.activated.connect(lambda reason: self.reveal() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def apply_hotkeys(self, initial=False):
        candidate = None
        try:
            capture = normalize_hotkey(self.capture_key.text())
            ocr = normalize_hotkey(self.ocr_key.text())
            if capture == ocr:
                raise ValueError("两个功能不能使用同一个快捷键")
            from pynput import keyboard
            candidate = keyboard.GlobalHotKeys({
                pynput_hotkey(capture): lambda: self.capture_requested.emit(False),
                pynput_hotkey(ocr): lambda: self.capture_requested.emit(True),
            })
            # Check asynchronous startup errors without blocking the Qt UI.
            candidate.start()
        except Exception as exc:
            if candidate:
                candidate.stop()
            message = str(exc)
            if "X connection" in message or "platform is not supported" in message:
                message = "当前环境没有可用的桌面键盘监听，请在本机桌面运行；Linux 请使用 X11"
            self.report_hotkey_error(message)
            return
        previous = self.listener
        self.listener = candidate
        if previous:
            previous.stop()
        self.settings.setValue("capture_key", capture)
        self.settings.setValue("ocr_key", ocr)
        self.settings.sync()
        self.status.setText(f"快捷键监听已启动：截图 {capture}；识字 {ocr}（系统占用可能影响触发）")
        QTimer.singleShot(800, lambda: self.check_listener(candidate))

    def check_listener(self, listener):
        if self.listener is listener and not listener.is_alive():
            self.report_hotkey_error("系统未能启动键盘监听，请检查辅助功能/输入监控权限或桌面会话类型")

    def report_hotkey_error(self, message):
        self.status.setText(f"快捷键不可用：{message}。仍可使用窗口或托盘按钮。")

    def capture(self, auto_ocr=False):
        if self.busy:
            self.status.setText("请等待当前识别完成后再截图")
            return
        if self.capturing:
            return
        self.capturing = True
        self.was_visible = self.isVisible()
        self.hide()
        QTimer.singleShot(250, lambda: self.start_capture(auto_ocr))

    def start_capture(self, auto_ocr):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is None:
            self.capture_cancelled()
            return
        snapshot = screen.grabWindow(0)
        if snapshot.isNull():
            self.capture_cancelled()
            QMessageBox.warning(self, "截图失败", "无法读取屏幕，请检查屏幕录制权限。Linux 建议使用 X11 会话。")
            return
        if self.overlay:
            self.overlay.deleteLater()
        self.overlay = CaptureOverlay(screen, snapshot, auto_ocr)
        self.overlay.selected.connect(self.captured)
        self.overlay.cancelled.connect(self.capture_cancelled)
        self.overlay.show()
        self.overlay.activateWindow()
        self.overlay.setFocus()

    def capture_cancelled(self):
        self.capturing = False
        if self.was_visible:
            self.reveal()

    def captured(self, pixmap, action):
        self.capturing = False
        self.set_image(pixmap)
        self.reveal()
        if action == "copy":
            self.copy_image()
        elif action == "save":
            self.save_image()
        elif action == "ocr":
            self.recognize()

    def set_image(self, pixmap):
        self.image = pixmap
        self.text.clear()
        self.update_preview()
        self.status.setText(f"已载入图片：{pixmap.width()} × {pixmap.height()}")

    def update_preview(self):
        if not self.image.isNull():
            self.preview.setPixmap(self.image.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_preview()

    def open_image(self):
        if self.busy:
            self.status.setText("请等待当前识别完成后再打开图片")
            return
        path, _ = QFileDialog.getOpenFileName(self, "打开图片", "", "图片 (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            pixmap = QPixmap(path)
            if pixmap.isNull():
                QMessageBox.warning(self, "打开失败", "无法读取这张图片")
            else:
                self.set_image(pixmap)

    def copy_image(self):
        if not self.image.isNull():
            QApplication.clipboard().setPixmap(self.image)
            self.status.setText("截图已复制，可直接粘贴到微信或其他应用")

    def save_image(self):
        if self.image.isNull():
            return
        default = str(Path.home() / f"截图_{datetime.now():%Y%m%d_%H%M%S}.png")
        path, _ = QFileDialog.getSaveFileName(self, "保存截图", default, "PNG 图片 (*.png)")
        if path:
            if not path.lower().endswith(".png"):
                path += ".png"
            if not self.image.save(path, "PNG"):
                QMessageBox.warning(self, "保存失败", "请检查目标文件夹是否可写")
            else:
                self.status.setText(f"已保存：{path}")

    def recognize(self):
        if self.busy or self.image.isNull():
            return
        self.busy = True
        self.ocr_started = perf_counter()
        self.recognize_button.setEnabled(False)
        self.status.setText("正在本地识别…")
        self.ocr_requested.emit(self.image.toImage().copy(), self.precise.isChecked())

    def ocr_finished(self, text):
        self.busy = False
        self.recognize_button.setEnabled(True)
        self.text.setPlainText(text)
        elapsed = perf_counter() - self.ocr_started
        self.status.setText(f"识别完成 · {len(text)} 个字符 · {elapsed:.2f} 秒" if text else f"未识别到文字 · {elapsed:.2f} 秒，可尝试精细识别")

    def ocr_failed(self, message):
        self.busy = False
        self.recognize_button.setEnabled(True)
        self.status.setText(message)

    def reveal(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if self.tray.isVisible():
            self.hide()
            event.ignore()
        else:
            event.accept()

    def shutdown(self):
        if self.listener:
            self.listener.stop()
        if self.overlay:
            self.overlay.hide()
        self.tray.hide()
        self.thread.quit()
        self.thread.wait()


def show_initial_window(window, autostart=False):
    # Never hide the app if the system has no tray from which to restore it.
    if not autostart or not window.tray.isVisible():
        window.show()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("青截")
    app.setApplicationVersion(__version__)
    window = MainWindow()
    app.aboutToQuit.connect(window.shutdown)
    show_initial_window(window, "--autostart" in sys.argv)
    sys.exit(app.exec())
