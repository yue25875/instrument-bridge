"""用合成信号自测 YIN：确认算法本身会不会把 E4 判成 E3。

构造一个"吉他味"的信号（基频 + 若干泛音 + 一点噪声），
分别用 E2/E3/E4 的音高生成，看 YIN 报回来的是不是对的。
"""

from __future__ import annotations

import os
import sys

import numpy as np

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace", line_buffering=True)
    except Exception:  # noqa: BLE001
        pass

# 把项目根目录加进 sys.path，这样从 tests/ 里也能 import src.*
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.notes import freq_to_midi, midi_to_name  # noqa: E402
from src.pitch import yin  # noqa: E402

SR = 48000
WINDOW = 2048


def guitar_tone(freq: float, n: int, sr: int, seed: int = 0) -> np.ndarray:
    """模拟拨弦音：基频 + 递减泛音 + 轻微噪声。"""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / sr
    # 泛音幅度：真实吉他二次、三次谐波经常很强
    amps = [1.0, 0.7, 0.5, 0.35, 0.25, 0.15, 0.1]
    x = np.zeros(n)
    for k, a in enumerate(amps, start=1):
        x += a * np.sin(2 * np.pi * freq * k * t)
    # 拨弦的指数衰减
    env = np.exp(-t * 3.0)
    x *= env
    # 一点白噪声，模拟麦克风底噪
    x += rng.normal(0, 0.002, n)
    return x / (np.max(np.abs(x)) + 1e-12) * 0.5


def test_note(midi: int, reps: int = 5) -> None:
    from src.notes import midi_to_freq

    freq_true = midi_to_freq(midi)
    name = midi_to_name(midi)
    print(f"\n=== {name} (MIDI {midi}, {freq_true:.2f} Hz) ===")
    for i in range(reps):
        x = guitar_tone(freq_true, WINDOW, SR, seed=i)
        res = yin(x, SR, min_freq=70, max_freq=1400, threshold=0.15, silence_db=-80)
        if res is None:
            print(f"  [{i}] -> None (没测出来)")
            continue
        f, conf = res
        m = int(round(freq_to_midi(f)))
        verdict = "OK" if m == midi else f"!! 错成 {midi_to_name(m)}"
        print(f"  [{i}] {f:8.2f} Hz  conf={conf:.2f}  -> {midi_to_name(m):<4} {verdict}")


def main() -> None:
    # E2(空弦低音E) / E3 / E4(1弦空弦)
    for midi in (40, 52, 64):
        test_note(midi)

    print("\n=== 加更多噪声的情况 ===")
    rng = np.random.default_rng(0)
    freq_true = 329.63  # E4
    t = np.arange(WINDOW) / SR
    x = np.sin(2 * np.pi * freq_true * t)
    x += rng.normal(0, 0.05, WINDOW)  # 噪声很强
    res = yin(x, SR, min_freq=70, max_freq=1400, threshold=0.15, silence_db=-80)
    if res:
        f, conf = res
        m = int(round(freq_to_midi(f)))
        print(f"  强噪声 E4 -> {f:.2f} Hz conf={conf:.2f} -> {midi_to_name(m)}")
    else:
        print("  强噪声 E4 -> None")


if __name__ == "__main__":
    main()
