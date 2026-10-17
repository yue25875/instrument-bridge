"""实时音量表：直观看到麦克风有没有收到声音。

用法：
    .venv\\Scripts\\python.exe mic_meter.py --device 17

然后对着麦克风说话 / 拍手 / 弹吉他，看进度条动不动。
条子完全不动 = 麦克风没工作（静音开关 / 选错设备 / 系统音量被拉低）。
"""

from __future__ import annotations

import argparse
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


class Ring:
    def __init__(self, size: int) -> None:
        self.size = size
        self._b = np.zeros(size, dtype=np.float32)
        self._l = threading.Lock()

    def push(self, block: np.ndarray) -> None:
        n = len(block)
        if n == 0:
            return
        with self._l:
            if n >= self.size:
                self._b[:] = block[-self.size :]
            else:
                self._b[:-n] = self._b[n:]
                self._b[-n:] = block

    def snap(self) -> np.ndarray:
        with self._l:
            return self._b.copy()


def bar(db: float, floor: float = -80.0, ceil: float = 0.0, width: int = 50) -> str:
    frac = (db - floor) / (ceil - floor)
    frac = max(0.0, min(1.0, frac))
    n = int(frac * width)
    return "#" * n + "." * (width - n)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--device", default=None)
    p.add_argument("--sr", type=int, default=48000)
    p.add_argument("--window", type=int, default=1024)
    args = p.parse_args()

    dev = int(args.device) if args.device and str(args.device).isdigit() else args.device
    ring = Ring(args.window)

    def cb(indata, frames, t, status):  # noqa: ARG001
        ring.push(indata[:, 0].copy())

    print(f"设备: {dev}")
    print("对着麦克风说话、拍手、弹吉他，看条子动不动。Ctrl+C 退出\n")
    print(f"{'当前':>8}  {'峰值':>7}  {'':<50}")
    print("-" * 72)

    peak = -120.0
    try:
        with sd.InputStream(device=dev, samplerate=args.sr, blocksize=256,
                            channels=1, dtype="float32", callback=cb):
            while True:
                time.sleep(0.05)
                fr = ring.snap()
                rms = float(np.sqrt(np.mean(fr.astype(np.float64) ** 2)))
                db = 20.0 * np.log10(rms + 1e-12)
                peak = max(peak, db)
                print(f"\r{db:8.1f}  {peak:7.1f}  {bar(db)}", end="", flush=True)
    except KeyboardInterrupt:
        print("\n\n已退出。")
    except Exception as exc:  # noqa: BLE001
        print(f"\n[错误] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
