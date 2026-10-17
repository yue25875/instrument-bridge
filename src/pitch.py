"""YIN 音高检测算法（纯 numpy 实现，无原生依赖）。

选择 YIN 而不是"FFT 取峰值"的原因：
    吉他单音的谐波（2 次、3 次）经常比基频还强，FFT 取峰值会把八度听错。
    YIN 的累积均值归一化差异函数在结构上就是为了压制倍频错误。

参考：de Cheveigné & Kawahara (2002), "YIN, a fundamental frequency
estimator for speech and music".
"""

from __future__ import annotations

import numpy as np


def _difference_function(x: np.ndarray, tau_max: int) -> np.ndarray:
    """计算 YIN 的差异函数 d(tau)，tau in [0, tau_max]。

    d(tau) = sum_{j=0}^{w-1} (x[j] - x[j+tau])^2
    """
    n = x.shape[0]
    w = n - tau_max
    if w <= 0:
        raise ValueError(f"窗口太短：n={n}, tau_max={tau_max}")

    # 前缀和，用于 O(1) 求任意窗口能量
    cs = np.empty(n + 1, dtype=np.float64)
    cs[0] = 0.0
    np.cumsum(x * x, out=cs[1:])

    sq = cs[w:] - cs[: n + 1 - w]                  # 长度 tau_max + 1
    cross = np.correlate(x, x[:w], mode="valid")   # 长度 tau_max + 1

    d = sq[0] + sq - 2.0 * cross
    return np.maximum(d, 0.0)


def yin(
    frame: np.ndarray,
    sample_rate: float,
    min_freq: float = 70.0,
    max_freq: float = 1400.0,
    threshold: float = 0.15,
    silence_db: float = -50.0,
) -> tuple[float, float] | None:
    """对一帧音频估计基频。

    Returns:
        (freq_hz, confidence) ；confidence in [0, 1]，越大越可信。
        无法判定时返回 None。
    """
    x = np.asarray(frame, dtype=np.float64)
    n = x.shape[0]
    if n < 64:
        return None

    rms = float(np.sqrt(np.mean(x * x)))
    if rms <= 0.0:
        return None
    # 用 dBFS 而不是线性 RMS 做门限：人耳和工程上都是按 dB 说话的，
    # 而且 dB 尺度和房间底噪的实测值能直接对上。
    rms_db = 20.0 * np.log10(rms + 1e-12)
    if rms_db < silence_db:
        return None

    tau_min = max(2, int(np.floor(sample_rate / max_freq)))
    tau_max = min(n // 2, int(np.ceil(sample_rate / min_freq)))
    if tau_max - tau_min < 3:
        return None

    d = _difference_function(x, tau_max)

    # 累积均值归一化差异函数
    cmnd = np.ones_like(d)
    cum = np.cumsum(d)
    denom = cum[1 : tau_max + 1]
    taus = np.arange(1, tau_max + 1, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        cmnd[1:] = np.where(denom > 0, d[1:] * taus / denom, 1.0)

    # 绝对阈值：第一个低于阈值的局部最小
    tau_est = -1
    for tau in range(tau_min, tau_max):
        if cmnd[tau] < threshold:
            while tau + 1 < tau_max and cmnd[tau + 1] < cmnd[tau]:
                tau += 1
            tau_est = tau
            break

    if tau_est < 0:
        # 没找到足够可信的周期，退回全局最小
        tau_est = int(np.argmin(cmnd[tau_min:tau_max])) + tau_min
        if cmnd[tau_est] > 0.60:
            return None

    # 抛物线插值，把 tau 精确到小数
    if 0 < tau_est < tau_max:
        a, b, c = cmnd[tau_est - 1], cmnd[tau_est], cmnd[tau_est + 1]
        denom = a - 2.0 * b + c
        shift = 0.5 * (a - c) / denom if abs(denom) > 1e-12 else 0.0
    else:
        shift = 0.0

    tau_refined = tau_est + shift
    if tau_refined <= 0:
        return None

    freq = float(sample_rate / tau_refined)
    if not (min_freq <= freq <= max_freq):
        return None

    confidence = float(np.clip(1.0 - cmnd[tau_est], 0.0, 1.0))
    return freq, confidence


def _spectrum_db(frame: np.ndarray, sample_rate: float):
    """返回 (freqs, 相对最强峰归一化的 dB 谱)。"""
    w = np.hanning(len(frame))
    spec = np.abs(np.fft.rfft(frame * w))
    freqs = np.fft.rfftfreq(len(frame), d=1.0 / sample_rate)
    peak = float(spec.max())
    if peak <= 0.0:
        return freqs, None
    return freqs, 20.0 * np.log10(spec / peak + 1e-12)


def _energy_db(freqs: np.ndarray, spec_db: np.ndarray, hz: float, bins: int = 2) -> float:
    """取某频率附近的峰值能量（dB，相对全帧最强峰）。"""
    i = int(np.argmin(np.abs(freqs - hz)))
    lo = max(0, i - bins)
    hi = min(len(spec_db), i + bins + 1)
    return float(spec_db[lo:hi].max())


def correct_octave(
    frame: np.ndarray,
    sample_rate: float,
    f0: float,
    max_freq: float = 1400.0,
    min_gain_db: float = 10.0,
    harmonic_limit_hz: float = 5000.0,
) -> float:
    """用频谱交叉验证修正"次谐波"型八度错误（报低了一个八度）。

    判别依据是**奇次谐波**，不是"2 倍频更强"：

      - 真实基频 f0：谐波在 f0, 2f0, 3f0, 4f0 ... 都存在，**3f0 有能量**。
      - 次谐波错误（真正基频是 2f0）：能量在 2f0, 4f0, 6f0 ...
        而 3f0 相当于真实基频的 1.5 倍，**那里没有能量**。

    所以只有当 3f0 明显弱于 2f0 和 4f0 时，才判定 f0 是次谐波，乘 2 修正。

    早期版本用"2 倍频比基频强就翻倍"，会在高音弦上误伤：
    吉他高音弦的基频本来就可能弱于二次谐波，那样会把 E4 错改成 E5。
    """
    freqs, spec_db = _spectrum_db(frame, sample_rate)
    if spec_db is None:
        return f0

    def e(hz: float) -> float | None:
        if hz > harmonic_limit_hz:
            return None
        return _energy_db(freqs, spec_db, hz)

    e2 = e(2.0 * f0)
    e3 = e(3.0 * f0)
    e4 = e(4.0 * f0)
    if e2 is None or e3 is None or e4 is None or 2.0 * f0 > max_freq:
        # 谐波超出分析范围，信息不足，不动
        return f0

    # 3 次谐波必须明显弱于 2、4 次，才认为是次谐波错误
    weaker_than_even = min(e2, e4) - e3
    if weaker_than_even >= min_gain_db:
        return 2.0 * f0
    return f0
