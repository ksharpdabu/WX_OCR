"""Portable shortcut validation, independent of the desktop backend."""
import re


def normalize_hotkey(text: str) -> str:
    aliases = {"control": "ctrl", "command": "cmd", "meta": "cmd", "option": "alt"}
    parts = [aliases.get(p.strip().lower(), p.strip().lower()) for p in text.split("+")]
    modifiers = {"ctrl", "alt", "shift", "cmd"}
    if len(parts) < 2 or any(not p for p in parts) or len(set(parts)) != len(parts):
        raise ValueError("请使用修饰键 + 按键，例如 Ctrl+Alt+A")
    if any(p not in modifiers for p in parts[:-1]) or parts[-1] in modifiers:
        raise ValueError("修饰键应放在前面，最后填写一个字母、数字或 F1–F12")
    if not re.fullmatch(r"[a-z0-9]|f(?:[1-9]|1[0-2])", parts[-1]):
        raise ValueError("最后一个键应为字母、数字或 F1–F12")
    ordered = [m for m in ("ctrl", "alt", "shift", "cmd") if m in parts[:-1]]
    return "+".join(ordered + [parts[-1]])


def pynput_hotkey(text: str) -> str:
    parts = normalize_hotkey(text).split("+")
    return "+".join(f"<{p}>" if len(p) > 1 else p for p in parts)
