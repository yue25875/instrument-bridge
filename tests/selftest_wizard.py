"""建表向导的解析函数自测（不需要游戏和麦克风）。"""

from __future__ import annotations

import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace", line_buffering=True)
    except Exception:  # noqa: BLE001
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from setup_wizard import midi_to_name, parse_note  # noqa: E402

CASES = [
    # (输入, 期望 MIDI)
    ("C4", 60),
    ("c4", 60),
    ("C#4", 61),
    ("Db4", 61),
    ("D4", 62),
    ("E4", 64),
    ("F4", 65),
    ("G4", 67),
    ("A4", 69),
    ("B4", 71),
    ("C5", 72),
    ("60", 60),
    ("48", 48),
    ("C3", 48),
]


def main() -> int:
    failed = 0
    for text, expect in CASES:
        got = parse_note(text)
        ok = got == expect
        if not ok:
            failed += 1
        print(f"  {text!r:<8} -> {got!r:<6} 期望 {expect}  {'OK' if ok else 'FAIL'}")

    for text in ("", "xyz", "H4", "C", "--"):
        got = parse_note(text)
        ok = got is None
        if not ok:
            failed += 1
        print(f"  {text!r:<8} -> {got!r:<6} 期望 None  {'OK' if ok else 'FAIL'}")

    # midi_to_name 反向验证
    for midi, expect in ((60, "C4"), (61, "C#4"), (72, "C5"), (48, "C3")):
        got = midi_to_name(midi)
        ok = got == expect
        if not ok:
            failed += 1
        print(f"  {midi} -> {got:<4} 期望 {expect}  {'OK' if ok else 'FAIL'}")

    print()
    print(f"失败 {failed} 个")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
