"""Opt-in Windows login startup for the current user (no administrator rights)."""
import subprocess
import sys
from pathlib import Path

SUPPORTED = sys.platform == "win32"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "QingJie"


def _registry():
    if not SUPPORTED:
        raise OSError("当前系统暂不支持开机启动设置")
    import winreg
    return winreg


def startup_command():
    if getattr(sys, "frozen", False):
        args = [sys.executable, "--autostart"]
    else:
        executable = Path(sys.executable)
        pythonw = executable.with_name("pythonw.exe")
        args = [str(pythonw if pythonw.is_file() else executable),
                str(Path(__file__).resolve().parents[1] / "main.py"), "--autostart"]
    # Quote paths with spaces according to Windows command-line rules.
    return subprocess.list2cmdline(args)


def is_enabled():
    registry = _registry()
    try:
        with registry.OpenKey(registry.HKEY_CURRENT_USER, RUN_KEY, 0, registry.KEY_READ) as key:
            value, value_type = registry.QueryValueEx(key, VALUE_NAME)
            return value_type == registry.REG_SZ and bool(value)
    except FileNotFoundError:
        return False


def set_enabled(enabled):
    registry = _registry()
    if enabled:
        with registry.CreateKeyEx(registry.HKEY_CURRENT_USER, RUN_KEY, 0, registry.KEY_SET_VALUE) as key:
            registry.SetValueEx(key, VALUE_NAME, 0, registry.REG_SZ, startup_command())
    else:
        try:
            with registry.OpenKey(registry.HKEY_CURRENT_USER, RUN_KEY, 0, registry.KEY_SET_VALUE) as key:
                registry.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            pass
