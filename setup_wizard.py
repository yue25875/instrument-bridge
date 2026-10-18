"""键位表建表向导：帮你为自己的游戏生成 profiles/games/xxx.json

为什么需要它：
    目前只内置了《异环》钢琴的键位表。换一个游戏，键位映射就得重新做。
    这个向导把"逐个按键、记录音高、生成配置"的过程自动化。

流程：
    1. 找到游戏窗口
    2. 逐个发送按键，你听它发出什么音，输入音名
    3. 可选：自动推导黑键（Shift/Ctrl + 白键）
    4. 生成 JSON

用法：
    .venv\\Scripts\\python.exe setup_wizard.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace", line_buffering=True)
    except Exception:  # noqa: BLE001
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.keys import find_window, focus_window, send_action  # noqa: E402

NOTE_NAMES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
MIDI_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

# 常见演奏界面的默认按键（3 排 × 7 键）
DEFAULT_LAYOUT = "q w e r t y u a s d f g h j z x c v b n m"

# 游戏窗口标题的常见候选
DEFAULT_TITLES = ["异环  ", "NTEGame", "原神", "Genshin Impact"]


def midi_to_name(midi: int) -> str:
    return f"{MIDI_NAMES[midi % 12]}{midi // 12 - 1}"


def parse_note(text: str) -> int | None:
    """解析音名或 MIDI 号。支持 C4 / c#4 / Db4 / 60。"""
    s = text.strip()
    if not s:
        return None
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    m = re.fullmatch(r"([A-Ga-g])([#b♯♭]?)(-?\d+)", s)
    if not m:
        return None
    letter = m.group(1).upper()
    acc = m.group(2)
    octave = int(m.group(3))
    midi = NOTE_NAMES[letter] + (octave + 1) * 12
    if acc in ("#", "♯"):
        midi += 1
    elif acc in ("b", "♭"):
        midi -= 1
    return midi


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return "q"


def parse_title_candidates(raw: str) -> list[str]:
    """用户输入的标题。支持带尾随空格（用引号包住），否则原样 + 补空格版本。"""
    raw = raw.strip()
    if not raw:
        return list(DEFAULT_TITLES)
    # 保留引号内的原始内容（可能带空格）
    m = re.fullmatch(r'["\'](.*)["\']', raw)
    if m:
        return [m.group(1)]
    # 同时试原始、加一个空格、加两个空格
    return [raw, raw + " ", raw + "  "]


def main() -> int:
    print("=" * 60)
    print("  键位表建表向导")
    print("=" * 60)
    print()
    print("你需要：游戏开着 + 已进入乐器界面。")
    print()

    # ---------- 1. 找窗口 ----------
    raw = ask("游戏窗口标题（留空=自动尝试常见标题）: ")
    candidates = parse_title_candidates(raw)
    hwnd = find_window(candidates)
    if hwnd == 0:
        print(f"\n[错误] 找不到窗口。试过: {candidates}")
        print("提示: Windows 的窗口标题可能带尾随空格。")
        print("     用引号包起来可以保留空格，例如: \"异环  \"")
        print("     也可以运行 list_devices.py 旁边的窗口枚举思路自己查。")
        return 1
    print(f"\n找到窗口: 句柄 {hwnd}"    )
    focus_window(hwnd)

    # ---------- 2. 按键布局 ----------
    print()
    print("键盘布局：从低到高、从左到右的按键顺序，空格分隔。")
    print("默认是三排各 7 键的常见布局：")
    print(f"  {DEFAULT_LAYOUT}")
    raw = ask(f"直接回车用默认，或输入你自己的: ")
    keys = raw.split() if raw.strip() else DEFAULT_LAYOUT.split()
    if not keys:
        print("[错误] 按键序列为空")
        return 1
    for k in keys:
        if k.lower() not in ("a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k",
                             "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v",
                             "w", "x", "y", "z"):
            print(f"[错误] 不认识的键: {k}")
            return 1

    # ---------- 3. 逐个按键 ----------
    print()
    print("=" * 60)
    print("开始。每按一个键，听游戏发出什么音，然后输入音名。")
    print("  支持: C4 / D#3 / Db3 / 60")
    print("  s = 跳过这个键    q = 提前结束")
    print("=" * 60)
    print()

    mapping: dict[int, str] = {}
    used_notes: set[int] = set()
    quit_early = False

    for i, key in enumerate(keys, start=1):
        while True:
            send_action(hwnd, key.lower())
            time.sleep(0.15)
            ans = ask(f"[{i}/{len(keys)}] 按了 {key.upper():<2} -> 听到什么音？ ")
            if ans.lower() == "q":
                print("提前结束。")
                quit_early = True
                break
            if ans.lower() == "s":
                print("  跳过")
                break
            midi = parse_note(ans)
            if midi is None:
                print("  没看懂，重试。格式: C4 / D#3 / 60")
                continue
            if midi in mapping:
                print(f"  注意: {midi_to_name(midi)} 已经有按键 {mapping[midi]}，会被 {key} 覆盖")
            mapping[midi] = key.lower()
            used_notes.add(midi)
            print(f"  记录: {midi_to_name(midi)} -> {key.upper()}")
            break
        if quit_early:
            break

    if not mapping:
        print("\n[错误] 一个键都没记录，退出。")
        return 1

    lo, hi = min(mapping), max(mapping)

    # ---------- 4. 黑键 ----------
    white_actions = dict(mapping)
    print()
    print("=" * 60)
    print("黑键（半音）怎么按？")
    print("  1) Shift + 下方白键 = 升半音")
    print("  2) Ctrl  + 上方白键 = 降半音")
    print("  3) 跳过（只支持白键）")
    print("=" * 60)
    choice = ask("选择 [1/2/3，默认 3]: ") or "3"

    if choice in ("1", "2"):
        added = 0
        for midi in range(lo, hi + 1):
            if midi in mapping:
                continue
            if choice == "1":
                lower = midi - 1
                if lower in white_actions:
                    mapping[midi] = f"shift+{white_actions[lower]}"
                    added += 1
            else:
                upper = midi + 1
                if upper in white_actions:
                    mapping[midi] = f"ctrl+{white_actions[upper]}"
                    added += 1
        print(f"自动推导了 {added} 个黑键。")
    else:
        print("跳过黑键。")

    # ---------- 5. 生成 JSON ----------
    print()
    name = ask("给这个键位表起个名字 [默认: 我的游戏]: ") or "我的游戏"
    safe = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", name).strip("_") or "custom"

    profile = {
        "_comment": "由 setup_wizard.py 生成。可以在游戏里逐个按键验证。",
        "name": name,
        "window_titles": candidates,
        "midi_range": [lo, hi],
        "hold_seconds": 0.03,
        "keys": {str(k): v for k, v in sorted(mapping.items())},
    }

    # 生成的文件要放在用户找得到的地方：
    #   exe 模式下 = exe 所在目录（_MEIPASS 是临时解压目录，程序退出就没了）
    #   源码模式 = 脚本所在目录
    if getattr(sys, "frozen", False):
        root = os.path.dirname(os.path.abspath(sys.executable))
    else:
        root = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(root, "profiles", "games")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{safe}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 60)
    print(f"已生成: {out_path}")
    print(f"  音域: {midi_to_name(lo)} ~ {midi_to_name(hi)}")
    print(f"  映射: {len(mapping)} 个键")
    print()
    print("下一步：")
    print(f"  .venv\\Scripts\\python.exe live_to_game.py --profile profiles/games/{safe}.json")
    print()
    print("建议先用 calibrate.py 听一遍确认，再正式弹。")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
