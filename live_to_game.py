"""麦克风 → 音高检测 → 异环钢琴按键。

整条链路：
    麦克风采集 → YIN 音高检测 → 八度修正 → 起音判定
              → 折叠到游戏音域 → 键位映射 → PostMessage 发送

用法：
    .venv\\Scripts\\python.exe live_to_game.py --device 17
    .venv\\Scripts\\python.exe live_to_game.py --device 17 --dry-run   # 只打印不发送

退出：Ctrl+C
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import threading
import time
from collections import deque

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

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_ACTIVATE = 0x0006
WA_CLICKACTIVE = 2

# 虚拟键码
KEY_VK = {
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45, "f": 0x46, "g": 0x47,
    "h": 0x48, "i": 0x49, "j": 0x4A, "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E,
    "o": 0x4F, "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54, "u": 0x55,
    "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59, "z": 0x5A,
    "shift": 0xA0,  # 左 Shift
    "ctrl": 0xA2,   # 左 Ctrl
}


class RingBuffer:
    """定长环形缓冲：音频回调线程写入，主线程取最新一窗。"""

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


def load_profile(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fold_into_range(midi: int, lo: int, hi: int) -> int:
    """把音高按八度折叠进游戏音域，保留音名（音级不变）。"""
    while midi < lo:
        midi += 12
    while midi > hi:
        midi -= 12
    return midi


def find_game_window(titles: list[str]) -> int:
    user32 = ctypes.windll.user32
    for t in titles:
        h = user32.FindWindowW(None, t)
        if h:
            return h
    return 0


def pick_default_device() -> int | None:
    """没指定 --device 时自动挑输入设备：优先 WASAPI，其次采样率高的。

    这样换台电脑不用改设备编号。
    """
    try:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
    except Exception:  # noqa: BLE001
        return None

    best: tuple[int, float] | None = None
    for i, d in enumerate(devices):
        if d["max_input_channels"] <= 0:
            continue
        api = hostapis[d["hostapi"]]["name"]
        score = (1000.0 if "WASAPI" in api else 0.0) + d["default_samplerate"] / 1000.0
        if best is None or score > best[1]:
            best = (i, score)
    return best[0] if best else None


def make_sender(hwnd: int, hold: float):
    """返回一个 send(midi) 函数，把 MIDI 音符号发成游戏按键。"""
    user32 = ctypes.windll.user32

    def vk_params(vk: int):
        scan = user32.MapVirtualKeyW(vk, 0)
        down = 1 | (scan << 16)
        up = down | 0xC0000000
        return down, up

    def tap(vk: int) -> None:
        down, up = vk_params(vk)
        user32.PostMessageW(hwnd, WM_KEYDOWN, vk, down)
        time.sleep(hold)
        user32.PostMessageW(hwnd, WM_KEYUP, vk, up)

    def send(action: str) -> None:
        """action 形如 'z' / 'shift+z' / 'ctrl+c'。"""
        parts = action.split("+")
        modifier = parts[0] if len(parts) > 1 else None
        key = parts[-1]

        if modifier:
            mvk = KEY_VK[modifier]
            mdown, mup = vk_params(mvk)
            user32.PostMessageW(hwnd, WM_KEYDOWN, mvk, mdown)
            time.sleep(0.002)
            tap(KEY_VK[key])
            time.sleep(0.001)
            user32.PostMessageW(hwnd, WM_KEYUP, mvk, mup)
        else:
            tap(KEY_VK[key])

    return send


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="麦克风 → 异环钢琴")
    p.add_argument("--device", default=None, help="输入设备编号（见 list_devices.py）")
    p.add_argument("--sr", type=int, default=48000)
    p.add_argument("--block", type=int, default=512)
    p.add_argument("--window", type=int, default=2048)
    p.add_argument("--min-freq", type=float, default=70.0)
    p.add_argument("--max-freq", type=float, default=1400.0)
    p.add_argument("--threshold", type=float, default=0.15)
    p.add_argument("--min-conf", type=float, default=0.65)
    p.add_argument("--gate-db", type=float, default=-38.0, help="静音门限(dBFS)，--gate-auto 时忽略")
    p.add_argument(
        "--gate-auto",
        action="store_true",
        help="自适应门限：根据环境底噪自动算，换麦克风/拾音器后不用手调",
    )
    p.add_argument(
        "--low-latency",
        action="store_true",
        help="低延迟模式：窗口 1024(约21ms)、块 256、音域下限提到 110Hz。"
        "注意会覆盖 --window/--block/--min-freq",
    )
    p.add_argument("--stable", type=int, default=2)
    p.add_argument("--onset-db", type=float, default=8.0)
    p.add_argument("--onset-window", type=int, default=10)
    p.add_argument("--no-octave-fix", action="store_true")
    p.add_argument("--hold", type=float, default=0.03, help="按键按住时长（秒），默认 0.03")
    p.add_argument("--retrigger", type=float, default=0.12, help="同一个音最短重触发间隔（秒）")
    p.add_argument("--dry-run", action="store_true", help="只打印要发什么键，不真的发送")
    p.add_argument("--verbose", action="store_true", help="每帧打印检测细节")
    p.add_argument(
        "--refocus-every",
        type=float,
        default=0.0,
        help="每隔几秒把游戏切回前台。默认 0=不抢焦点（推荐：自己先点一下游戏窗口）",
    )
    p.add_argument(
        "--transpose",
        type=int,
        default=24,
        help="整体移调半音数。必须是 12 的整数倍才能保持音名不变。"
        "+12=吉他C3进低音区，+24=吉他C3进中音区，+36=吉他C3进高音区",
    )
    p.add_argument("--profile", default=None, help="游戏键位表 JSON 路径")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    # 低延迟模式：窗口减半、块变小、音域下限定到 110Hz（C3 以上够用）
    if args.low_latency:
        args.window = 1024
        args.block = 256
        if args.min_freq < 110.0:
            args.min_freq = 110.0
    root = os.path.dirname(os.path.abspath(__file__))
    profile_path = args.profile or os.path.join(root, "profiles", "games", "nte-piano.json")
    profile = load_profile(profile_path)
    keymap = {int(k): v for k, v in profile["keys"].items()}
    lo, hi = profile["midi_range"]

    # 找窗口
    hwnd = find_game_window(profile.get("window_titles", ["异环  "]))
    if hwnd == 0 and not args.dry_run:
        print("[错误] 没找到游戏窗口。先把异环切到游戏世界并打开钢琴。", file=sys.stderr)
        print("       调试时可以用 --dry-run 先在终端里看效果。", file=sys.stderr)
        return 1
    user32 = ctypes.windll.user32

    def focus_game() -> None:
        """把游戏切到前台。异环只有在自己是前台窗口时才收键盘输入。"""
        if not hwnd:
            return
        user32.ShowWindow(hwnd, 9)          # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        user32.SendMessageW(hwnd, WM_ACTIVATE, WA_CLICKACTIVE, 0)

    if hwnd:
        focus_game()
        time.sleep(0.3)
        print(f"游戏窗口句柄 = {hwnd}")
    else:
        print("[dry-run] 没找到游戏窗口，只打印不发送")

    sender = make_sender(hwnd, args.hold)
    device = int(args.device) if args.device and str(args.device).isdigit() else args.device
    if device is None:
        device = pick_default_device()
        if device is not None:
            try:
                print(f"自动选择输入设备: [{device}] {sd.query_devices(device)['name']}")
            except Exception:  # noqa: BLE001
                pass

    ring = RingBuffer(args.window)

    def callback(indata, frames, t, status):  # noqa: ARG001
        if status:
            print(f"[音频] {status}", file=sys.stderr)
        ring.push(indata[:, 0].copy())

    print(f"音域折叠范围: MIDI {lo}~{hi} ({midi_to_name(lo)} ~ {midi_to_name(hi)})")
    print(f"移调: {args.transpose:+d} 半音")
    print(
        f"  参照: 吉他 C3({48}) -> 游戏 {midi_to_name(48 + args.transpose)}   "
        f"吉他 C4({60}) -> 游戏 {midi_to_name(60 + args.transpose)}"
    )
    print(
        f"检测窗口: {args.window} 样本 ({args.window / args.sr * 1000:.0f} ms)   "
        f"门限: {'自适应' if args.gate_auto else f'{args.gate_db:.0f} dBFS'}"
    )
    print("弹吉他试试。Ctrl+C 退出\n")

    hop = args.block / args.sr
    candidate = None
    stable_count = 0
    silent_frames = 0
    last_sent_midi = None
    last_sent_time = 0.0
    last_attack_time = 0.0
    last_refocus = 0.0
    level_history: deque[float] = deque(maxlen=args.onset_window)
    noise_history: deque[float] = deque(maxlen=400)   # 自适应门限用的底噪历史

    try:
        with sd.InputStream(
            device=device, samplerate=args.sr, blocksize=args.block,
            channels=1, dtype="float32", callback=callback,
        ):
            while True:
                time.sleep(hop)
                # 定期抢回前台：异环失去焦点就不收按键
                if args.refocus_every > 0 and hwnd:
                    t_now = time.time()
                    if t_now - last_refocus >= args.refocus_every:
                        last_refocus = t_now
                        if user32.GetForegroundWindow() != hwnd:
                            focus_game()
                frame = ring.snapshot()

                rms = float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)))
                db = 20.0 * np.log10(rms + 1e-12)
                level_history.append(db)
                noise_history.append(db)

                # 门限：固定值 or 根据底噪自动算
                if args.gate_auto and len(noise_history) >= 50:
                    # 底噪用 20% 分位（避开弹奏时的响帧），再留 26dB 余量。
                    # 实测：安静房间底噪约 -75dBFS，环境噪声峰值能到 -54，吉他 -20~-35。
                    floor_db = float(np.percentile(np.fromiter(noise_history, dtype=float), 20))
                    gate_db = max(-58.0, min(-32.0, floor_db + 26.0))
                else:
                    # 启动头 0.5 秒样本不够，先用固定值兜底
                    gate_db = args.gate_db

                is_onset = (
                    args.onset_db <= 0
                    or len(level_history) < 3
                    or (db - min(level_history)) >= args.onset_db
                )

                res = yin(frame, args.sr, min_freq=args.min_freq, max_freq=args.max_freq,
                          threshold=args.threshold, silence_db=gate_db)

                if res is None:
                    silent_frames += 1
                    if silent_frames >= 5:
                        candidate = None
                        last_sent_midi = None
                    if args.verbose:
                        print(f"[帧] db={db:6.1f}  静音")
                    continue

                silent_frames = 0
                freq, conf = res
                if not args.no_octave_fix:
                    freq = correct_octave(frame, args.sr, freq, max_freq=args.max_freq)
                midi_raw = int(round(freq_to_midi(freq)))

                if conf < args.min_conf:
                    if args.verbose:
                        print(f"[帧] db={db:6.1f}  {midi_to_name(midi_raw):<4} conf={conf:.2f}  置信度不足")
                    candidate = None
                    stable_count = 0
                    continue

                if midi_raw == candidate:
                    stable_count += 1
                else:
                    candidate = midi_raw
                    stable_count = 1

                if args.verbose:
                    print(
                        f"[帧] db={db:6.1f}  {midi_to_name(midi_raw):<4} conf={conf:.2f} "
                        f"onset={int(is_onset)} stable={stable_count}"
                    )

                if stable_count < args.stable:
                    continue

                # 整体移调：所有音统一平移，保持旋律的相对音高不变。
                # 只有极少数超出游戏音域的音才回退到八度折叠（会造成局部跳变，
                # 所以尽量用 --transpose 让整段都落在音域内）。
                midi_game = midi_raw + args.transpose
                folded = False
                if midi_game < lo or midi_game > hi:
                    midi_game = fold_into_range(midi_game, lo, hi)
                    folded = True
                action = keymap.get(midi_game)
                if action is None:
                    continue

                now = time.time()
                # 什么时候触发：
                #   1. 音高变了（换音）
                #   2. 或者检测到新的起音，且距上次发送超过 retrigger 间隔（同一个音重复弹）
                changed = midi_game != last_sent_midi
                new_attack = is_onset and (now - last_sent_time) >= args.retrigger
                if not (changed or new_attack):
                    if args.verbose:
                        print(f"     跳过: 音未变={not changed} 无新起音={not new_attack}")
                    continue
                if is_onset:
                    last_attack_time = now

                last_sent_midi = midi_game
                last_sent_time = now

                shift = midi_game - midi_raw
                shift_txt = f" {shift:+d}" if shift else "   "
                fold_txt = "  [超范围已折叠]" if folded else ""
                line = (
                    f"  {midi_to_name(midi_raw):<4} -> {midi_to_name(midi_game):<4}"
                    f" {shift_txt}  键={action:<8} conf={conf:.2f} lvl={db:5.1f}dB{fold_txt}"
                )
                print(line)
                if not args.dry_run:
                    sender(action)
    except KeyboardInterrupt:
        print("\n已退出。")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"\n[错误] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
