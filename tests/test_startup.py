from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from wxocr import startup


class Registry:
    HKEY_CURRENT_USER = 1
    KEY_READ = 2
    KEY_SET_VALUE = 4
    REG_SZ = 1

    def __init__(self):
        self.values = {"AnotherApp": ("leave me alone", self.REG_SZ)}

    def OpenKey(self, *args):
        return nullcontext(self)

    CreateKeyEx = OpenKey

    def QueryValueEx(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name]

    def SetValueEx(self, key, name, reserved, kind, value):
        self.values[name] = (value, kind)

    def DeleteValue(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]


def test_register_remove_and_read_system_state(monkeypatch):
    registry = Registry()
    monkeypatch.setattr(startup, '_registry', lambda: registry)
    monkeypatch.setattr(startup.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(startup.sys, 'executable', r'C:\My Tools\QingJie.exe')
    assert not startup.is_enabled()
    startup.set_enabled(True)
    assert startup.is_enabled()
    assert registry.values[startup.VALUE_NAME][0] == '"C:\\My Tools\\QingJie.exe" --autostart'
    startup.set_enabled(False)
    startup.set_enabled(False)  # Already removed externally: disabling stays safe.
    assert not startup.is_enabled()
    assert registry.values == {"AnotherApp": ("leave me alone", registry.REG_SZ)}


def test_source_command_has_absolute_script_and_autostart_flag(monkeypatch):
    monkeypatch.setattr(startup.sys, 'frozen', False, raising=False)
    command = startup.startup_command()
    assert str(startup.Path(startup.__file__).resolve().parents[1] / 'main.py') in command
    assert command.endswith(' --autostart')


def test_permission_failure_reverts_checkbox(monkeypatch):
    from PySide6.QtWidgets import QApplication, QCheckBox, QLabel
    from wxocr.app import MainWindow
    app = QApplication.instance() or QApplication([])
    checkbox = QCheckBox()
    state = SimpleNamespace(autostart=checkbox, status=QLabel())

    def denied(enabled):
        raise PermissionError('access denied')

    monkeypatch.setattr(startup, 'set_enabled', denied)
    checkbox.toggled.connect(lambda enabled: MainWindow.set_autostart(state, enabled))
    checkbox.setChecked(True)
    assert not checkbox.isChecked()
    assert '失败' in state.status.text()
    checkbox.blockSignals(True)
    checkbox.setChecked(True)
    checkbox.blockSignals(False)
    checkbox.setChecked(False)
    assert checkbox.isChecked()


@pytest.mark.parametrize(('autostart', 'tray', 'expected_shown'), [
    (False, True, True), (True, True, False), (True, False, True),
])
def test_initial_visibility_policy(autostart, tray, expected_shown):
    from wxocr.app import show_initial_window
    shown = []
    window = SimpleNamespace(tray=SimpleNamespace(isVisible=lambda: tray), show=lambda: shown.append(True))
    show_initial_window(window, autostart)
    assert bool(shown) is expected_shown
