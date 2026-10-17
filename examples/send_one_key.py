# 往异环游戏窗口发送一个按键（Z），验证游戏是否接受程序发来的按键。
#
# 关键：真正的游戏窗口标题是 "异环  "（尾部有两个空格），进程是 HTGame.exe。
#       "NTEGame" 是启动器窗口，别发错。
#
# 运行前确认：
#   1. 游戏已经进入游戏世界（不是更新/启动器界面）
#   2. 游戏里已经打开钢琴界面

import ctypes
import time

user32 = ctypes.windll.user32

# ---------- 1. 找游戏窗口 ----------
# 先试真正的游戏窗口（注意尾部两个空格），找不到再退回启动器
hwnd = user32.FindWindowW(None, "异环  ")
if hwnd == 0:
    hwnd = user32.FindWindowW(None, "NTEGame")

print("句柄 =", hwnd)
if hwnd == 0:
    print("没找到游戏窗口，异环是不是没开？")
    raise SystemExit

# ---------- 2. 把游戏窗口切到前台并激活 ----------
user32.ShowWindow(hwnd, 9)          # 9 = SW_RESTORE，恢复如果最小化了
time.sleep(0.2)
user32.SetForegroundWindow(hwnd)    # 切到前台
time.sleep(0.5)
user32.SendMessageW(hwnd, 0x0006, 2, 0)   # WM_ACTIVATE / WA_CLICKACTIVE

# ---------- 3. 准备 Z 键的参数 ----------
VK_Z = 0x5A                             # Z 键的虚拟键码（A=0x41 ... Z=0x5A）
scan = user32.MapVirtualKeyW(VK_Z, 0)   # 转换成硬件扫描码，游戏认这个
lparam_down = 1 | (scan << 16)          # 扫描码在高 16 位，最低位 1 = 按下
lparam_up = lparam_down | 0xC0000000    # 最高两位 11 = 抬起

# ---------- 4. 发送按下 → 停顿 → 抬起 ----------
# 0x0100 = WM_KEYDOWN, 0x0101 = WM_KEYUP
user32.PostMessageW(hwnd, 0x0100, VK_Z, lparam_down)
time.sleep(0.05)
user32.PostMessageW(hwnd, 0x0101, VK_Z, lparam_up)

print("已发送 Z 键")
