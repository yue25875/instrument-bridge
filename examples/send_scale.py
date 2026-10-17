# 给异环游戏窗口连发一串按键，用来确认游戏到底收不收程序发的按键。
#
# 发的是低音区 1~7：Z X C V B N M
#
# 运行前：游戏进入世界 + 打开钢琴界面

import ctypes
import time

user32 = ctypes.windll.user32

# ---------- 找真游戏窗口（"异环  " 尾部两个空格）----------
hwnd = user32.FindWindowW(None, "异环  ")
if hwnd == 0:
    hwnd = user32.FindWindowW(None, "NTEGame")
print("句柄 =", hwnd)
if hwnd == 0:
    print("没找到游戏窗口")
    raise SystemExit

# ---------- 切到前台 ----------
user32.ShowWindow(hwnd, 9)
time.sleep(0.2)
user32.SetForegroundWindow(hwnd)
time.sleep(0.5)
user32.SendMessageW(hwnd, 0x0006, 2, 0)   # WM_ACTIVATE

# ---------- 按键表 ----------
KEY_VK = {
    "Q": 0x51, "W": 0x57, "E": 0x45, "R": 0x52, "T": 0x54, "Y": 0x59, "U": 0x55,
    "A": 0x41, "S": 0x53, "D": 0x44, "F": 0x46, "G": 0x47, "H": 0x48, "J": 0x4A,
    "Z": 0x5A, "X": 0x58, "C": 0x43, "V": 0x56, "B": 0x42, "N": 0x4E, "M": 0x4D,
}

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101


def press(key: str, hold: float = 0.06) -> None:
    vk = KEY_VK[key]
    scan = user32.MapVirtualKeyW(vk, 0)
    down = 1 | (scan << 16)
    up = down | 0xC0000000
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, down)
    time.sleep(hold)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, up)


# ---------- 低音 1~7 ----------
sequence = ["Z", "X", "C", "V", "B", "N", "M"]
for i, k in enumerate(sequence, start=1):
    print(f"  {i}: {k}")
    press(k)
    time.sleep(0.25)

print("发送完毕")
