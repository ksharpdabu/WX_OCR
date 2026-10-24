import pytest
from wxocr.hotkeys import normalize_hotkey, pynput_hotkey


def test_aliases_and_order():
    assert normalize_hotkey(" Shift + Control + A ") == "ctrl+shift+a"
    assert normalize_hotkey("Command+Option+F12") == "alt+cmd+f12"
    assert pynput_hotkey("Ctrl+Alt+A") == "<ctrl>+<alt>+a"
    assert pynput_hotkey("Cmd+F2") == "<cmd>+<f2>"


@pytest.mark.parametrize("value", ["a", "ctrl+ctrl+a", "ctrl+", "a+ctrl", "ctrl+alt", "ctrl+F13", "ctrl+ab", "ctrl++a"])
def test_invalid_shortcuts(value):
    with pytest.raises(ValueError):
        normalize_hotkey(value)
