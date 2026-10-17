"""录一段真实音频存成 WAV，用来事后分析。

用途：把"弹 E4 却报 E3"这个现象的真实波形抓下来，
      离线看 FFT 频谱就知道是信号本身有 164Hz 成分，还是算法判错了。

用法：
    .venv\\Scripts\\python.exe record_sample.py --device 17 --seconds 12
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import wave

import numpy as np
import sounddevice as sd

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace", line_buffering=True)
    except Exception:  # noqa: BLE001
        pass


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--device", default=None)
    p.add_argument("--seconds", type=float, default=12.0)
    p.add_argument("--sr", type=int, default=48000)
    p.add_argument("--out", default=None)
    args = p.parse_args()

    device = int(args.device) if args.device and str(args.device).isdigit() else args.device
    blocks: list[np.ndarray] = []

    def cb(indata, frames, t, status):  # noqa: ARG001
        blocks.append(indata[:, 0].copy())

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
    os.makedirs(out_dir, exist_ok=True)
    out_path = args.out or os.path.join(out_dir, time.strftime("rec_%Y%m%d_%H%M%S.wav"))

    print(f"开始录音 {args.seconds:.0f} 秒。")
    print("请在这段时间里：")
    print("  1. 先安静 2 秒（录底噪）")
    print("  2. 然后弹 E4（1 弦空弦）5 次，每次之间停 1 秒")
    print()
    time.sleep(0.5)

    with sd.InputStream(device=device, samplerate=args.sr, blocksize=1024, channels=1, dtype="float32", callback=cb):
        for i in range(int(args.seconds)):
            print(f"\r  录音中... {i + 1}/{int(args.seconds)} 秒", end="", flush=True)
            time.sleep(1.0)

    print()
    if not blocks:
        print("[错误] 没收到音频")
        return 1

    audio = np.concatenate(blocks)
    pcm = np.clip(audio, -1.0, 1.0)
    pcm16 = (pcm * 32767).astype(np.int16)
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(args.sr)
        wf.writeframes(pcm16.tobytes())

    dur = len(audio) / args.sr
    peak_db = 20 * np.log10(np.max(np.abs(audio)) + 1e-12)
    print(f"已保存: {out_path}")
    print(f"时长 {dur:.1f}s  峰值 {peak_db:.1f} dBFS")
    print()
    print("把这个路径告诉助手，让它分析。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
