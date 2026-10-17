"""分析录好的 WAV：对比 YIN 结果和 FFT 频谱。

这是排查"八度错误"的关键工具：
  如果 YIN 报 164Hz，而 FFT 在 164Hz 处几乎没有能量、能量都在 329Hz 的谐波上，
  那就是算法判错了（认上了次谐波）。
  反之如果 FFT 在 164Hz 真有能量，那说明信号里确实有低八度成分。

用法：
    .venv\\Scripts\\python.exe analyze_wav.py samples\\rec_xxx.wav
    .venv\\Scripts\\python.exe analyze_wav.py samples\\rec_xxx.wav --frames 15
"""

from __future__ import annotations

import argparse
import os
import sys
import wave

import numpy as np

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace", line_buffering=True)
    except Exception:  # noqa: BLE001
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.notes import freq_to_midi, midi_to_name  # noqa: E402
from src.pitch import correct_octave, yin  # noqa: E402


def load_wav(path: str) -> tuple[np.ndarray, int]:
    with wave.open(path, "rb") as wf:
        sr = wf.getframerate()
        n = wf.getnframes()
        raw = wf.readframes(n)
        ch = wf.getnchannels()
        width = wf.getsampwidth()
    if width != 2:
        raise ValueError(f"只支持 16bit WAV，当前 {width * 8}bit")
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch)[:, 0]
    return data, sr


def spectral_peaks(frame: np.ndarray, sr: int, max_hz: float = 2000.0, top: int = 4):
    """返回帧内最强的几个频谱峰 (freq, rel_db)。"""
    w = np.hanning(len(frame))
    spec = np.abs(np.fft.rfft(frame * w))
    freqs = np.fft.rfftfreq(len(frame), d=1.0 / sr)
    valid = freqs <= max_hz
    spec, freqs = spec[valid], freqs[valid]
    if spec.max() <= 0:
        return []
    # 局部极大
    idx = np.where((spec[1:-1] > spec[:-2]) & (spec[1:-1] >= spec[2:]))[0] + 1
    if len(idx) == 0:
        idx = np.array([int(np.argmax(spec))])
    idx = idx[np.argsort(spec[idx])[::-1][:top]]
    peak = spec.max()
    return [(float(freqs[i]), float(20 * np.log10(spec[i] / peak + 1e-12))) for i in idx]


def energy_at(frame: np.ndarray, sr: int, hz: float, window_bins: int = 3) -> float:
    """指定频率附近的频谱能量（相对最强峰，dB）。"""
    w = np.hanning(len(frame))
    spec = np.abs(np.fft.rfft(frame * w))
    freqs = np.fft.rfftfreq(len(frame), d=1.0 / sr)
    peak = spec.max()
    if peak <= 0:
        return -120.0
    i = int(np.argmin(np.abs(freqs - hz)))
    lo = max(0, i - window_bins)
    hi = min(len(spec), i + window_bins + 1)
    return float(20 * np.log10(spec[lo:hi].max() / peak + 1e-12))


def note(freq: float) -> str:
    m = int(round(freq_to_midi(freq)))
    return f"{midi_to_name(m)}({m})"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("wav")
    p.add_argument("--frames", type=int, default=10, help="显示最响的多少帧")
    p.add_argument("--window", type=int, default=2048)
    p.add_argument("--hop", type=int, default=512)
    p.add_argument("--gate-db", type=float, default=-45.0)
    args = p.parse_args()

    audio, sr = load_wav(args.wav)
    print(f"文件   : {args.wav}")
    print(f"采样率 : {sr} Hz   时长: {len(audio) / sr:.2f}s")

    frames = []
    for start in range(0, len(audio) - args.window, args.hop):
        fr = audio[start : start + args.window]
        rms = float(np.sqrt(np.mean(fr * fr)))
        db = 20 * np.log10(rms + 1e-12)
        if db >= args.gate_db:
            frames.append((db, start, fr))

    if not frames:
        print(f"\n没有任何一帧超过 {args.gate_db} dBFS —— 录音里没有有效声音。")
        return 0

    print(f"有效帧 : {len(frames)} / {(len(audio) - args.window) // args.hop + 1}")
    frames.sort(key=lambda t: -t[0])

    print(f"\n=== 最响的 {args.frames} 帧：YIN vs 频谱峰 ===")
    print(f"{'电平':>7}  {'时间':>6}  {'YIN原始':<16} {'八度修正后':<16} {'频谱最强峰':<16} {'判定'}")
    for db, start, fr in frames[: args.frames]:
        res = yin(fr, sr, min_freq=70, max_freq=1400, threshold=0.15, silence_db=-120)
        peaks = spectral_peaks(fr, sr)
        sp_f, sp_db = peaks[0] if peaks else (0.0, -120.0)
        t = start / sr
        if res is None:
            print(f"{db:7.1f}  {t:6.2f}  {'(未测出)':<16} {'-':<16} {note(sp_f) + f' {sp_f:.0f}Hz':<16}")
            continue
        f, conf = res
        f_fix = correct_octave(fr, sr, f, max_freq=1400)
        m_sp = int(round(freq_to_midi(sp_f)))
        m_fix = int(round(freq_to_midi(f_fix)))
        tag = "一致" if m_fix == m_sp else "**不一致**"
        mark = " <-修正" if abs(f_fix - f) > 1e-6 else ""
        print(
            f"{db:7.1f}  {t:6.2f}  {note(f) + f' {f:.0f}Hz':<16} "
            f"{note(f_fix) + f' {f_fix:.0f}Hz':<16} {note(sp_f) + f' {sp_f:.0f}Hz':<16} {tag}{mark}"
        )

    # 对最响的一帧做谐波分析
    db, start, fr = frames[0]
    print(f"\n=== 最响那一帧({start / sr:.2f}s, {db:.1f}dB)的谐波结构 ===")
    res = yin(fr, sr, min_freq=70, max_freq=1400, threshold=0.15, silence_db=-120)
    print(f"YIN 结果: {note(res[0]) + f' {res[0]:.2f}Hz conf={res[1]:.2f}' if res else '(未测出)'}")
    print("频谱峰(前 6 个):")
    for f_hz, rel_db in spectral_peaks(fr, sr, top=6):
        print(f"   {f_hz:8.1f} Hz  {rel_db:+6.1f} dB  -> {note(f_hz)}")
    if res:
        f0 = res[0]
        print(f"\n以 YIN 结果 {f0:.1f}Hz 为基频，各次谐波能量:")
        for k in (1, 2, 3, 4, 5):
            e = energy_at(fr, sr, f0 * k)
            print(f"   {k}x = {f0 * k:8.1f} Hz   {e:+6.1f} dB")
        print(f"\n若 1x 很弱而 2x/3x 强，说明 YIN 认错了基频（真正的基频可能是 2x）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
