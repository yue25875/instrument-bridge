"""Windows 键盘注入：虚拟键码表 + PostMessage 发送。

把「往游戏窗口发一个键」这件事集中在这里，主程序和建表向导共用。

为什么用 PostMessage 而不是 SendInput：
    SendInput 会把按键送到系统当前的焦点窗口，需要抢系统输入焦点。
    PostMessage 直接往目标窗口的消息队列里塞消息，不需要抢焦点。
    但注意：很多游戏会自己检查是否在前台，不是前台仍然会忽略——
    所以发之前通常要先 focus_window()。
"""

from __future__ import annotations

import ctypes
import time

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_ACTIVATE = 0x0006
WA_CLICKACTIVE = 2

# 虚拟键码。修饰键用左边的（0xA0/0xA2），避免和右边区分导致游戏识别不到。
KEY_VK: dict[str, int] = {
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45, "f": 0x46, "g": 0x47,
    "h": 0x48, "i": 0x49, "j": 0x4A, "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E,
    "o": 0x4F, "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54, "u": 0x55,
    "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59, "z": 0x5A,
    "shift": 0xA0,   # 左 Shift
    "ctrl": 0xA2,    # 左 Ctrl
}

user32 = ctypes.windll.user32


def _vk_params(vk: int) -> tuple[int, int]:
    """返回 (按下时的 lparam, 抬起时的 lparam)。"""
    scan = user32.MapVirtualKeyW(vk, 0)
    down = 1 | (scan << 16)
    up = down | 0xC0000000
    return down, up


def tap(hwnd: int, vk: int, hold: float = 0.03) -> None:
    """按下一个键，保持 hold 秒，再抬起。"""
    down, up = _vk_params(vk)
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, down)
    time.sleep(hold)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, up)


def send_action(hwnd: int, action: str, hold: float = 0.03) -> None:
    """发送一个带可选修饰键的动作。

    action 形如 "z" / "shift+z" / "ctrl+c"。
    """
    parts = action.split("+")
    key = parts[-1].lower()
    modifier = parts[0].lower() if len(parts) > 1 else None

    if key not in KEY_VK:
        raise KeyError(f"未知按键: {key!r}")

    if modifier:
        if modifier not in KEY_VK:
            raise KeyError(f"未知修饰键: {modifier!r}")
        mvk = KEY_VK[modifier]
        mdown, mup = _vk_params(mvk)
        user32.PostMessageW(hwnd, WM_KEYDOWN, mvk, mdown)
        time.sleep(0.002)
        tap(hwnd, KEY_VK[key], hold)
        time.sleep(0.001)
        user32.PostMessageW(hwnd, WM_KEYUP, mvk, mup)
    else:
        tap(hwnd, KEY_VK[key], hold)


def focus_window(hwnd: int) -> None:
    """把窗口切到前台并激活。

    游戏通常在不是前台窗口时不收键盘输入，所以发键前先叫一下。
    """
    user32.ShowWindow(hwnd, 9)          # SW_RESTORE
    time.sleep(0.2)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.2)
    user32.SendMessageW(hwnd, WM_ACTIVATE, WA_CLICKACTIVE, 0)


def find_window(titles: list[str]) -> int:
    """按标题找窗口，找不到返回 0。"""
    for t in titles:
        h = user32.FindWindowW(None, t)
        if h:
            return h
    return 0
