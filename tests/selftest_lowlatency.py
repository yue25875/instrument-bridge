"""测试低延迟模式(窗口 1024)对音高检测的影响。

对比 2048(当前)和 1024(低延迟)在 C3~B5 各音上的准确率。
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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.notes import freq_to_midi, midi_to_freq, midi_to_name  # noqa: E402
from src.pitch import yin  # noqa: E402

SR = 48000


def guitar_tone(freq: float, n: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(n) / SR
    amps = [1.0, 0.7, 0.5, 0.35, 0.25, 0.15, 0.1]
    x = np.zeros(n)
    for k, a in enumerate(amps, start=1):
        x += a * np.sin(2 * np.pi * freq * k * t)
    x *= np.exp(-t * 3.0)
    x += rng.normal(0, 0.002, n)
    return x / (np.max(np.abs(x)) + 1e-12) * 0.5


def run(label: str, window: int, min_freq: float) -> None:
    print(f"\n=== {label} (window={window}, min_freq={min_freq}) ===")
    ok = 0
    total = 0
    for midi in range(48, 84):  # C3 ~ B5
        f = midi_to_freq(midi)
        hits = 0
        for seed in range(5):
            x = guitar_tone(f, window, seed=seed)
            res = yin(x, SR, min_freq=min_freq, max_freq=1400, threshold=0.15, silence_db=-80)
            total += 1
            if res is not None:
                m = int(round(freq_to_midi(res[0])))
                if m == midi:
                    hits += 1
                    ok += 1
        if hits < 5:
            print(f"  {midi_to_name(midi):<4} 命中 {hits}/5")
    pct = 100.0 * ok / total if total else 0
    print(f"  总准确率: {ok}/{total} = {pct:.1f}%")


def main() -> None:
    run("当前", 2048, 70)
    run("低延迟 A", 1024, 110)
    run("低延迟 B", 1024, 130)
    run("折中", 1536, 100)


if __name__ == "__main__":
    main()
