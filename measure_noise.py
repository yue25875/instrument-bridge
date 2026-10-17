"""测房间底噪：录几秒钟，报告 RMS 电平(dBFS)和峰值。

用途：给 live_pitch.py 的 --gate-db 定一个合理的门槛。
规则：门槛应该比底噪高 10~15 dB。

用法：
    .venv\\Scripts\\python.exe measure_noise.py --device 17 --seconds 5
"""

from __future__ import annotations

import argparse
import sys
import time

import numpy as np
import sounddevice as sd

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace", line_buffering=True)
    except Exception:  # noqa: BLE001
        pass


def dbfs(x: np.ndarray) -> float:
    rms = float(np.sqrt(np.mean(x * x)))
    return 20.0 * np.log10(rms + 1e-12)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--device", default=None)
    p.add_argument("--seconds", type=float, default=5.0)
    p.add_argument("--sr", type=int, default=48000)
    args = p.parse_args()

    device = int(args.device) if args.device is not None and str(args.device).isdigit() else args.device
    blocks: list[np.ndarray] = []

    def cb(indata, frames, t, status):  # noqa: ARG001
        blocks.append(indata[:, 0].copy())

    print(f"录音 {args.seconds} 秒，请保持安静（不要说话、不要弹琴）...")
    with sd.InputStream(device=device, samplerate=args.sr, blocksize=1024, channels=1, dtype="float32", callback=cb):
        time.sleep(args.seconds)

    if not blocks:
        print("[错误] 没收到任何音频")
        return 1

    audio = np.concatenate(blocks)
    # 按 100ms 切片，看每一片电平的分布
    hop = int(args.sr * 0.1)
    n = len(audio) // hop
    levels = np.array([dbfs(audio[i * hop : (i + 1) * hop]) for i in range(n)])

    print()
    print(f"总时长     : {len(audio) / args.sr:.1f} 秒")
    print(f"整体 RMS   : {dbfs(audio):7.1f} dBFS")
    print(f"峰值       : {20 * np.log10(np.max(np.abs(audio)) + 1e-12):7.1f} dBFS")
    print(f"最安静片段 : {levels.min():7.1f} dBFS")
    print(f"中位数片段 : {np.median(levels):7.1f} dBFS")
    print(f"最响片段   : {levels.max():7.1f} dBFS")
    print()
    print(f"建议 --gate-db 取 {levels.max() + 10:.0f} 附近（比最响的安静片段再高 10 dB）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
