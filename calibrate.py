"""校准工具：让游戏钢琴弹三个八度的 C 大调音阶，用来验证键位映射对不对。

会依次弹：
    低音区  Z X C V B N M      （按映射表应该是 C4 D4 E4 F4 G4 A4 B4）
    中音区  A S D F G H J      （应该是 C5 D5 E5 F5 G5 A5 B5）
    高音区  Q W E R T Y U      （应该是 C6 D6 E6 F6 G6 A6 B6）

用法：先在游戏里打开钢琴，然后运行本脚本，听就知道了。
"""

from __future__ import annotations

import ctypes
import time

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_ACTIVATE = 0x0006
WA_CLICKACTIVE = 2

VK = {
    "q": 0x51, "w": 0x57, "e": 0x45, "r": 0x52, "t": 0x54, "y": 0x59, "u": 0x55,
    "a": 0x41, "s": 0x53, "d": 0x44, "f": 0x46, "g": 0x47, "h": 0x48, "j": 0x4A,
    "z": 0x5A, "x": 0x58, "c": 0x43, "v": 0x56, "b": 0x42, "n": 0x4E, "m": 0x4D,
}

user32 = ctypes.windll.user32


def find_game() -> int:
    h = user32.FindWindowW(None, "异环  ")
    if h == 0:
        h = user32.FindWindowW(None, "NTEGame")
    return h


def focus(hwnd: int) -> None:
    user32.ShowWindow(hwnd, 9)
    time.sleep(0.2)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)
    user32.SendMessageW(hwnd, WM_ACTIVATE, WA_CLICKACTIVE, 0)


def press(hwnd: int, key: str, hold: float = 0.06) -> None:
    vk = VK[key]
    scan = user32.MapVirtualKeyW(vk, 0)
    down = 1 | (scan << 16)
    up = down | 0xC0000000
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, down)
    time.sleep(hold)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, up)


def play_row(hwnd: int, keys: str, name: str, gap: float = 0.45) -> None:
    print(f"  {name}: {' '.join(keys.upper())}")
    for k in keys:
        press(hwnd, k)
        time.sleep(gap)
    time.sleep(1.2)


def main() -> int:
    hwnd = find_game()
    if hwnd == 0:
        print("没找到游戏窗口，先开游戏并进入钢琴界面")
        return 1
    print(f"游戏窗口 = {hwnd}")
    focus(hwnd)

    print("即将弹三个八度的 C 大调音阶（do re mi fa sol la si）")
    print("请仔细听：每一组应该都是同一个音阶，只是越来越高\n")
    time.sleep(0.5)

    play_row(hwnd, "zxcvbnm", "低音区")
    play_row(hwnd, "asdfghj", "中音区")
    play_row(hwnd, "qwertyu", "高音区")

    print("\n弹完了。问自己三个问题：")
    print("  1. 每一组听起来是不是 do re mi fa sol la si（大调音阶）？")
    print("  2. 三组是不是一组比一组高？")
    print("  3. 有没有哪一组听起来是乱的、或者音程关系不对？")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
