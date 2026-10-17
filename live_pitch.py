"""实时音高检测演示：麦克风 -> YIN -> 屏幕打印音符。

这一版故意不接游戏。目的是先单独验证：
  1. 麦克风能不能收到干净的信号
  2. YIN 在木吉他上准不准（重点是会不会把八度听错）
  3. 你弹的每个音，检测到的音名对不对

用法：
    .venv\\Scripts\\python.exe live_pitch.py
    .venv\\Scripts\\python.exe live_pitch.py --device 1
    .venv\\Scripts\\python.exe live_pitch.py --debug      # 每帧刷新原始频率

退出：Ctrl+C
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from collections import deque

import numpy as np
import sounddevice as sd

from src.notes import cents_from_midi, freq_to_midi, midi_to_name
from src.pitch import correct_octave, yin

# Windows 控制台默认是 GBK，某些符号（如音分符号）编不出来会让程序直接崩。
# 这里让无法编码的字符降级成 '?'，而不是让整个程序挂掉。
# line_buffering=True 必须加：输出被管道/重定向接走时 Python 默认块缓冲，
# 不 flush 就会"程序在跑但屏幕什么都不显示"。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace", line_buffering=True)
    except Exception:  # noqa: BLE001
        pass


class RingBuffer:
    """定长环形缓冲：回调线程写入，主线程取最新一窗。"""

    def __init__(self, size: int) -> None:
        self.size = size
        self._buf = np.zeros(size, dtype=np.float32)
        self._lock = threading.Lock()

    def push(self, block: np.ndarray) -> None:
        n = block.shape[0]
        if n == 0:
            return
        with self._lock:
            if n >= self.size:
                self._buf[:] = block[-self.size :]
            else:
                self._buf[:-n] = self._buf[n:]
                self._buf[-n:] = block

    def snapshot(self) -> np.ndarray:
        with self._lock:
            return self._buf.copy()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="麦克风实时音高检测")
    p.add_argument("--device", default=None, help="输入设备编号或名字（见 list_devices.py）")
    p.add_argument("--sr", type=int, default=48000, help="采样率，默认 48000")
    p.add_argument("--block", type=int, default=512, help="音频块大小，默认 512")
    p.add_argument("--window", type=int, default=2048, help="检测窗口，默认 2048")
    p.add_argument("--min-freq", type=float, default=70.0, help="最低检测频率，默认 70Hz")
    p.add_argument("--max-freq", type=float, default=1400.0, help="最高检测频率，默认 1400Hz")
    p.add_argument("--threshold", type=float, default=0.15, help="YIN 阈值，越小越严格，默认 0.15")
    p.add_argument("--min-conf", type=float, default=0.65, help="最低置信度，低于此值忽略，默认 0.65")
    p.add_argument(
        "--gate-db",
        type=float,
        default=-38.0,
        help="静音门限(dBFS)，低于此电平直接判定为静音。用 measure_noise.py 测底噪后取底噪+20，默认 -50",
    )
    p.add_argument("--stable", type=int, default=2, help="连续多少帧一致才确认换音，默认 2")
    p.add_argument(
        "--onset-db",
        type=float,
        default=8.0,
        help="起音判定：电平比最近低点高出多少 dB 才算一次新的拨弦。0 = 关闭起音门控。默认 8",
    )
    p.add_argument("--onset-window", type=int, default=15, help="起音判定的回看帧数，默认 15 帧(约160ms)")
    p.add_argument(
        "--no-octave-fix",
        action="store_true",
        help="关闭八度修正（默认开启：用频谱交叉验证，防止 E4 被判成 E3）",
    )
    p.add_argument("--debug", action="store_true", help="每帧刷新显示原始频率")
    return p.parse_args()


def resolve_device(device: str | None) -> int | None:
    if device is None:
        return None
    try:
        return int(device)
    except ValueError:
        return device  # sounddevice 也接受名字子串


def main() -> int:
    args = parse_args()

    # 要测出最低频率 f，窗口至少得装下它的 2 个周期：window >= 2 * sr / f
    needed_window = int(args.sr / args.min_freq) * 2
    if args.window < needed_window:
        print(
            f"[警告] 窗口 {args.window} 对最低频率 {args.min_freq}Hz 偏短，"
            f"低音会测不准。建议窗口 >= {needed_window}",
            file=sys.stderr,
        )

    device = resolve_device(args.device)
    try:
        info = sd.query_devices(device, kind="input")
        default_sr = info["default_samplerate"]
    except Exception as exc:  # noqa: BLE001
        print(f"[错误] 打不开输入设备 {device!r}: {exc}", file=sys.stderr)
        print("       先运行 list_devices.py 看看有哪些设备。", file=sys.stderr)
        return 1

    if abs(default_sr - args.sr) > 1:
        print(f"[提示] 设备默认采样率是 {default_sr:.0f}，将强制使用 {args.sr}")

    ring = RingBuffer(args.window)

    def callback(indata, frames, time_info, status):  # noqa: ARG001
        if status:
            print(f"[音频状态] {status}", file=sys.stderr)
        ring.push(indata[:, 0].copy())

    print(f"设备   : [{device if device is not None else 'default'}] {info['name']}")
    print(f"采样率 : {args.sr} Hz   窗口: {args.window} 样本 ({args.window / args.sr * 1000:.1f} ms)")
    print(f"范围   : {args.min_freq:.0f} – {args.max_freq:.0f} Hz")
    print("按 Ctrl+C 退出\n")

    hop_seconds = args.block / args.sr
    last_reported: int | None = None
    candidate: int | None = None
    stable_count = 0
    silent_frames = 0
    level_history: deque[float] = deque(maxlen=args.onset_window)

    try:
        with sd.InputStream(
            device=device,
            samplerate=args.sr,
            blocksize=args.block,
            channels=1,
            dtype="float32",
            callback=callback,
        ):
            while True:
                time.sleep(hop_seconds)
                frame = ring.snapshot()

                # 电平每帧都算，不管有没有检测出音高——起音判定依赖它
                frame_rms = float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)))
                frame_db = 20.0 * np.log10(frame_rms + 1e-12)
                level_history.append(frame_db)
                baseline_db = min(level_history)
                # 起音：当前电平比最近的低点高出 onset_db。持续音的这个条件会自然失效，
                # 于是"衰减过程中算法飘到泛音"就不会再冒出新音符。
                is_onset = (
                    args.onset_db <= 0.0
                    or len(level_history) < 3
                    or (frame_db - baseline_db) >= args.onset_db
                )

                result = yin(
                    frame,
                    args.sr,
                    min_freq=args.min_freq,
                    max_freq=args.max_freq,
                    threshold=args.threshold,
                    silence_db=args.gate_db,
                )

                if result is None:
                    silent_frames += 1
                    # 静音够久才清除"上次报的音"，这样同一个音再弹一次还能报出来
                    if silent_frames >= 5:
                        last_reported = None
                    if args.debug:
                        print(
                            f"\r  (静音) lvl={frame_db:5.1f}dB                      ",
                            end="",
                            flush=True,
                        )
                    candidate, stable_count = None, 0
                    continue

                silent_frames = 0
                freq, conf = result
                # 频谱交叉验证：修正 YIN 的"次谐波"型八度错误（E4 -> E3）
                if not args.no_octave_fix:
                    freq = correct_octave(frame, args.sr, freq, max_freq=args.max_freq)
                midi_float = freq_to_midi(freq)
                midi = int(round(midi_float))
                cents = cents_from_midi(midi_float)
                onset_mark = " ATTACK" if is_onset else ""

                if args.debug:
                    print(
                        f"\r  {midi_to_name(midi):<4} {freq:7.2f}Hz "
                        f"{cents:+6.1f}c  conf={conf:.2f}  lvl={frame_db:5.1f}dB{onset_mark:<7}",
                        end="",
                        flush=True,
                    )

                if conf < args.min_conf:
                    candidate, stable_count = None, 0
                    continue

                if midi == candidate:
                    stable_count += 1
                else:
                    candidate, stable_count = midi, 1

                # 起音门控：不是新拨弦，就不报新音符
                if not is_onset:
                    continue

                if stable_count >= args.stable and midi != last_reported:
                    last_reported = midi
                    print(
                        f"  >> {midi_to_name(midi):<4} (MIDI {midi:3d})  "
                        f"{freq:7.2f}Hz  {cents:+6.1f}c  conf={conf:.2f}  lvl={frame_db:5.1f}dB"
                    )
    except KeyboardInterrupt:
        print("\n\n已退出。")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"\n[错误] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
