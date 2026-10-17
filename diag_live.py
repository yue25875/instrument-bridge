"""诊断用：每 0.5 秒打印一次电平、检测结果、门限判定。

用来回答"到底卡在哪一环"：
  - 电平一直很低 → 麦克风没收到声音
  - 电平够但没检测 → 算法/门限问题
  - 检测到但游戏没反应 → 发送环节问题
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time

import numpy as np
import sounddevice as sd

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace", line_buffering=True)
    except Exception:  # noqa: BLE001
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.notes import freq_to_midi, midi_to_name  # noqa: E402
from src.pitch import correct_octave, yin  # noqa: E402


class Ring:
    def __init__(self, size):
        self.size = size
        self._b = np.zeros(size, dtype=np.float32)
        self._l = threading.Lock()

    def push(self, block):
        n = len(block)
        if n == 0:
            return
        with self._l:
            if n >= self.size:
                self._b[:] = block[-self.size:]
            else:
                self._b[:-n] = self._b[n:]
                self._b[-n:] = block

    def snap(self):
        with self._l:
            return self._b.copy()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--device", default=None)
    p.add_argument("--sr", type=int, default=48000)
    p.add_argument("--window", type=int, default=2048)
    p.add_argument("--gate-db", type=float, default=-38.0)
    p.add_argument("--interval", type=float, default=0.5)
    p.add_argument("--seconds", type=float, default=30.0)
    args = p.parse_args()

    dev = int(args.device) if args.device and str(args.device).isdigit() else args.device
    ring = Ring(args.window)

    def cb(indata, frames, t, status):  # noqa: ARG001
        ring.push(indata[:, 0].copy())

    print(f"{'时间':>6}  {'电平':>8}  {'门限':>7}  {'检测结果'}")
    print("-" * 60)
    t0 = time.time()
    last = 0.0
    try:
        with sd.InputStream(device=dev, samplerate=args.sr, blocksize=512,
                            channels=1, dtype="float32", callback=cb):
            while True:
                now = time.time() - t0
                if now > args.seconds:
                    break
                time.sleep(0.05)
                if now - last < args.interval:
                    continue
                last = now
                fr = ring.snap()
                rms = float(np.sqrt(np.mean(fr.astype(np.float64) ** 2)))
                db = 20.0 * np.log10(rms + 1e-12)
                res = yin(fr, args.sr, min_freq=70, max_freq=1400,
                          threshold=0.15, silence_db=args.gate_db)
                if res is None:
                    why = "静音(低于门限)" if db < args.gate_db else "有声音但测不出音高"
                    print(f"{now:6.1f}  {db:8.1f}  {args.gate_db:7.1f}  {why}")
                    continue
                f, conf = res
                f = correct_octave(fr, args.sr, f, max_freq=1400)
                m = int(round(freq_to_midi(f)))
                mark = "OK" if conf >= 0.65 else "低置信"
                print(f"{now:6.1f}  {db:8.1f}  {args.gate_db:7.1f}  {midi_to_name(m):<4} {f:7.1f}Hz conf={conf:.2f} {mark}")
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
