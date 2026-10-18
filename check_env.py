"""环境自检：跑这个可以知道你的电脑和这个程序兼不兼容。

它只读信息，不改任何设置，也不需要管理员权限。

用法：
    .venv\\Scripts\\python.exe check_env.py
"""

from __future__ import annotations

import ctypes
import os
import platform
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace", line_buffering=True)
    except Exception:  # noqa: BLE001
        pass


def section(title: str) -> None:
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def ok(label: str, value: str) -> None:
    print(f"  {label:<20} {value}")


def run_ps(cmd: str, timeout: int = 15) -> str:
    """跑一条 PowerShell 命令拿输出，失败返回空字符串。"""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return out.stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def main() -> int:
    section("系统")
    ok("Windows", platform.platform())
    ok("架构", platform.machine())
    ok("Python", sys.version.split()[0])
    try:
        is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        is_admin = False
    ok("管理员权限", "是" if is_admin else "否（本程序不需要）")

    section("显示适配器")
    gpus = run_ps("Get-PnpDevice -Class Display | Where-Object Status -eq 'OK' | "
                  "Select-Object -ExpandProperty FriendlyName")
    if gpus:
        for line in gpus.splitlines():
            print(f"  - {line.strip()}")
        if any(k in gpus for k in ("Virtual", "虚拟", "MuMu", "Nox", "LDPlayer", "Parsec")):
            print()
            print("  注意：检测到虚拟显示适配器。这类设备通常由安卓模拟器或串流软件安装，")
            print("        与本项目无关。如果不需要，可以卸载对应软件，")
            print("        或在设备管理器里禁用该设备。")
    else:
        print("  读取失败（不影响本程序，本程序不访问显卡）")

    section("音频输入设备")
    try:
        import sounddevice as sd
        hostapis = sd.query_hostapis()
        devices = sd.query_devices()
        inputs = [(i, d) for i, d in enumerate(devices) if d["max_input_channels"] > 0]
        if not inputs:
            print("  ❌ 没有找到任何音频输入设备")
            print("     本程序需要麦克风才能工作。")
        else:
            for i, d in inputs:
                api = hostapis[d["hostapi"]]["name"]
                print(f"  [{i:2d}] {d['name']}")
                print(f"       通道={d['max_input_channels']}  "
                      f"采样率={d['default_samplerate']:.0f}  API={api}")
            try:
                default_in = sd.query_devices(kind="input")["name"]
                ok("默认输入", default_in)
            except Exception:  # noqa: BLE001
                print("  ⚠ 无法确定默认输入设备，运行时用 --device 指定")
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ sounddevice 初始化失败: {exc}")
        print("     通常是没装依赖，先跑 一键安装.bat")

    section("可能冲突的软件")
    conflicts = {
        "MuMu": "MuMu 安卓模拟器（会装虚拟显示适配器）",
        "Nox": "夜神模拟器",
        "LDPlayer": "雷电模拟器",
        "obs": "OBS（屏幕捕获可能抢焦点）",
        "Parsec": "Parsec 远程串流",
        "Sunshine": "Sunshine 串流",
        "ToDesk": "ToDesk 远程控制",
        "Sunlogin": "向日葵远程控制",
        "EasyAntiCheat": "EAC 反作弊",
        "BEService": "BattlEye 反作弊",
        "vgc": "Vanguard 反作弊",
        "Razer": "雷蛇外设软件",
        "Logi": "罗技外设软件",
    }
    found = False
    try:
        out = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="replace",
        ).stdout
        for key, desc in conflicts.items():
            if key.lower() in out.lower():
                print(f"  - {desc}")
                found = True
    except Exception:  # noqa: BLE001
        pass
    if not found:
        print("  未检测到常见冲突软件")

    section("游戏窗口")
    try:
        user32 = ctypes.windll.user32
        for title in ("异环  ", "NTEGame", "原神", "Genshin Impact"):
            h = user32.FindWindowW(None, title)
            if h:
                print(f"  ✅ 找到窗口: {title!r} (句柄 {h})")
                break
        else:
            print("  没有找到已知的游戏窗口（游戏没开，或者用了别的游戏）")

        # 顺便检查系统所有可见窗口标题，方便用户找自己的游戏
        print()
        print("  当前所有可见窗口（找找你的游戏叫什么）:")
        import ctypes.wintypes as wt

        titles = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
        def enum_proc(hwnd, lparam):  # noqa: ARG001
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    cap = length + 2
                    buf = ctypes.create_unicode_buffer(cap)
                    user32.GetWindowTextW(hwnd, buf, cap)
                    if buf.value.strip():
                        titles.append(buf.value)
            return True

        user32.EnumWindows(enum_proc, 0)
        for t in titles[:15]:
            print(f"    {t!r}")
        if len(titles) > 15:
            print(f"    ... 还有 {len(titles) - 15} 个")
    except Exception as exc:  # noqa: BLE001
        print(f"  读取窗口失败: {exc}")

    section("结论")
    print("  这个程序只做两件事：读麦克风、往游戏窗口发按键消息。")
    print("  它不安装驱动、不修改显示设置、不访问显卡、不需要管理员权限。")
    print()
    print("  如果运行后出现显卡异常、显示设置变化等问题，")
    print("  请先检查设备管理器里的显卡状态 和 Windows 事件查看器，")
    print("  这类问题通常由驱动崩溃或硬件问题引起。")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
