"""列出所有音频输入设备，用来确认麦克风编号。"""

import sounddevice as sd


def main() -> None:
    print("=== 主机 API ===")
    for i, h in enumerate(sd.query_hostapis()):
        print(f"  [{i}] {h['name']}")

    print("\n=== 音频输入设备 ===")
    devices = sd.query_devices()
    for i, d in enumerate(devices):
        if d["max_input_channels"] <= 0:
            continue
        api = sd.query_hostapis(d["hostapi"])["name"]
        mark = " <-- 默认" if i == sd.default.device[0] else ""
        print(
            f"  [{i:2d}] {d['name']}\n"
            f"       通道={d['max_input_channels']}  "
            f"默认采样率={d['default_samplerate']:.0f}  "
            f"API={api}{mark}"
        )

    try:
        default_in = sd.query_devices(kind="input")
        print(f"\n默认输入设备: [{sd.default.device[0]}] {default_in['name']}")
    except Exception as exc:  # noqa: BLE001
        print(f"\n默认输入设备获取失败: {exc}")


if __name__ == "__main__":
    main()
