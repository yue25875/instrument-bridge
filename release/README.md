# 下载

**给只想用、不想装 Python 的人：**

下载 instrument-bridge.exe，双击运行即可。

## 用法

1. 游戏里打开钢琴界面
2. 双击 instrument-bridge.exe
3. 黑窗口出现后，**鼠标点一下游戏窗口**（让游戏获得焦点）
4. 手离开鼠标键盘，开始弹
5. 按 Ctrl+C 退出

## 注意

- **钢琴界面没打开时不要运行**，按键会变成普通游戏操作
- 能弹的音域是吉他 C3 ~ B3
- 详细说明见项目根目录的 README.md

## 它是怎么来的

用 PyInstaller 从本仓库源码打包：

``
pip install pyinstaller
pyinstaller --onefile --console --name instrument-bridge --add-data "profiles;profiles" live_to_game.py
``

想自己打或想审计代码，看仓库源码。