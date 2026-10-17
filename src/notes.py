"""频率、MIDI 音符号、音名之间的换算。

MIDI 音符号约定：A4 = 69 = 440Hz。这是整个项目和游戏键位表之间的通用货币。
"""

from __future__ import annotations

import math

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def freq_to_midi(freq: float, a4: float = 440.0) -> float:
    """频率 -> 连续 MIDI 音符号（带小数，用于算音分偏差）。"""
    return 69.0 + 12.0 * math.log2(freq / a4)


def midi_to_freq(midi: float, a4: float = 440.0) -> float:
    """MIDI 音符号 -> 频率。"""
    return a4 * 2.0 ** ((midi - 69.0) / 12.0)


def midi_to_name(midi: int) -> str:
    """MIDI 音符号 -> 音名，例如 60 -> 'C4'。"""
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def cents_from_midi(midi_float: float) -> float:
    """距离最近半音的音分偏差，范围 (-50, 50]。"""
    nearest = round(midi_float)
    return (midi_float - nearest) * 100.0
