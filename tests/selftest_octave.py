"""专测八度修正会不会"过度纠正"。

现实中的高音吉他弦，基频常常比二次谐波弱。
如果 correct_octave 只看"2 倍处更强"就翻倍，就会把正确的高音判成高八度。
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
from src.pitch import correct_octave, yin  # noqa: E402

SR = 48000
WINDOW = 2048


def make(freq: float, amps: list[float], seed: int = 0, noise: float = 0.002) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(WINDOW) / SR
    x = np.zeros(WINDOW)
    for k, a in enumerate(amps, start=1):
        x += a * np.sin(2 * np.pi * freq * k * t)
    x *= np.exp(-t * 3.0)
    x += rng.normal(0, noise, WINDOW)
    return x / (np.max(np.abs(x)) + 1e-12) * 0.5


def run(label: str, midi: int, amps: list[float]) -> None:
    f_true = midi_to_freq(midi)
    expected = midi_to_name(midi)
    print(f"\n--- {label}: {expected} ({f_true:.1f}Hz), 泛音幅度={amps} ---")
    for seed in range(3):
        x = make(f_true, amps, seed=seed)
        res = yin(x, SR, min_freq=70, max_freq=1400, threshold=0.15, silence_db=-80)
        if res is None:
            print(f"  [{seed}] YIN: (未测出)")
            continue
        f, conf = res
        f_fix = correct_octave(x, SR, f, max_freq=1400)
        yin_note = midi_to_name(int(round(freq_to_midi(f))))
        fix_note = midi_to_name(int(round(freq_to_midi(f_fix))))
        flag_yin = "OK" if yin_note == expected else "WRONG"
        flag_fix = "OK" if fix_note == expected else "WRONG"
        changed = " (被改动)" if abs(f_fix - f) > 1e-6 else ""
        print(
            f"  [{seed}] YIN {yin_note:<4} {flag_yin:<5} | "
            f"修正后 {fix_note:<4} {flag_fix:<5}{changed}"
        )


def main() -> None:
    print("=" * 70)
    print("八度修正鲁棒性测试：修正应该只纠错，不能把对的改错")
    print("=" * 70)

    normal = [1.0, 0.7, 0.5, 0.35, 0.25, 0.15]
    weak_fund = [0.15, 1.0, 0.6, 0.4, 0.25, 0.15]  # 基频很弱，二次谐波最强
    very_weak = [0.05, 1.0, 0.8, 0.5, 0.3, 0.15]   # 基频几乎消失

    for midi, name in ((40, "E2低音"), (52, "E3中音"), (64, "E4高音"), (67, "G4") , (71, "B4")):
        run(f"{name}-正常音色", midi, normal)

    print("\n" + "=" * 70)
    print("下面是高风险情况：高音 + 基频很弱")
    print("=" * 70)
    for midi in (64, 67, 71):
        run("高音+弱基频", midi, weak_fund)
    for midi in (64, 67, 71):
        run("高音+极弱基频", midi, very_weak)


if __name__ == "__main__":
    main()
