# 下载

**给只想用、不想装 Python 的人：**

下载 `instrument-bridge.exe`，双击运行即可。

## 用法

1. 游戏里打开钢琴界面
2. 双击 `instrument-bridge.exe`
3. 黑窗口出现后，**鼠标点一下游戏窗口**（让游戏获得焦点）
4. 手离开鼠标键盘，开始弹
5. 按 Ctrl+C 退出

## 换别的游戏

这个 exe 内置的键位表只有《异环》钢琴。想换成别的游戏：

**双击 `建表向导.bat`**（需要和 exe 放在同一目录）

或者在命令行运行：

```
instrument-bridge.exe --wizard
```

向导会让你逐个按键、输入听到的音名，自动生成键位表到 `profiles/games/` 下。

之后运行时指定：

```
instrument-bridge.exe --profile profiles\games\你的游戏.json
```

## 其它

**查看所有可用参数：**

```
instrument-bridge.exe --help
```

**注意**

- **钢琴界面没打开时不要运行**，按键会变成普通游戏操作
- 游戏窗口必须是前台
- 能弹的音域是吉他 C3 ~ B3
- 详细说明见项目根目录的 README.md

## 它是怎么来的

用 PyInstaller 从本仓库源码打包：

```
pip install pyinstaller
pyinstaller --onefile --console --name instrument-bridge --hidden-import setup_wizard --add-data "profiles;profiles" live_to_game.py
```

想自己打或想审计代码，看仓库源码。

## 本程序不做什么

不安装驱动、不修改显示设置、不访问显卡、不需要管理员权限。
它只做两件事：读麦克风、往游戏窗口发按键消息。

如果运行后出现显卡或显示异常，请先检查设备管理器里的显卡状态和 Windows 事件查看器，
这类问题通常由驱动崩溃或硬件原因引起。
