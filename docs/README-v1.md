# Octane「蜘蛛热」Windows 桌宠 V1

原生 Python + PySide6 桌面窗口。直接使用提供的三张 PNG；不生成角色、不重绘、不抠图、不覆盖原文件。原素材中的银白服饰、紫色护目镜、面罩、披肩、机械腿与特效均保留。

## 启动

已打包版本：双击 `dist\OctaneDesktopPet\OctaneDesktopPet.exe`。整个 `OctaneDesktopPet` 文件夹一起复制即可在 Windows x64 运行，无须安装 Python。不要只复制 EXE。

源码版本：双击 `launch.bat`。首次运行需要 Python 3.10+ x64 和网络；脚本会建立 `.venv`、安装 `requirements.txt`。本机也支持使用 Codex 自带的 Python。需要查看错误时使用 PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
.\.venv\Scripts\python.exe .\main.py
```

## 操作

- 左键按住角色拖动；拖动期间冻结动作及移动，松开后继续，可拖至另一块屏幕。
- 右键角色或系统托盘图标：自动切换、固定待机、固定行走、扎针后冲刺、暂停、退出。
- 手动选动作会关闭自动切换，重新勾选即可恢复。再次选择正在进行的 Run 不会重复扎针；先离开 Run 再进入才重新扎针。
- 自动模式以 3～7 秒间隔切换，轻微斜向移动，在当前显示器工作区边缘转向，避开任务栏。跨屏通过拖拽完成。
- 无边框、背景透明、保持置顶；菜单打开时暂时停止移动。系统托盘菜单可在角色不易点击时退出。

## 素材与参数

配置在 `assets/animations.json`，PNG 独立存放在 `assets/`。修改后重启生效；打包后也使用 EXE 同目录下的 `assets/`。

| 素材 | 实际尺寸 | 布局与帧数 | 用途 |
|---|---|---|---|
| idle.png | 1536 × 1024 | 3 列 × 2 行，6 帧 | 待机循环 |
| walk.png | 1536 × 1024 | 3 列 × 2 行，6 帧 | 小碎步循环 |
| run.png | 1774 × 887 | 4 列 × 2 行，8 帧 | 前 4 帧起跑准备，后 4 帧冲刺循环 |

帧号从 **0** 开始，先从左到右、再从上到下。Run 默认为 `stim: [0,1,2,3]`、`run: [4,5,6,7]`：取出注射器、扎针与起跑准备只播放一次，结束后自动进入循环。准备阶段原地播放，随后以冲刺速度移动。

Run 的帧划分按提供图片的姿势顺序推定；若后续素材定义不同，只需改配置。当前三张图的上下排并非严格等高，已配置独立取帧矩形（Idle 在 y=522～525、Walk 在 y=520、Run 在 y=474 分排），避免均分时切掉脚部或带入上一排脚部。`canvas` 将不同高度的帧底部对齐，稳定播放比例。原图中部分跨帧特效仍可能在边缘有接缝；程序不擅自修图。正式导出素材最好每帧独立留出边距，角色大小、脚底基准保持一致。

- `display_height`：显示画布边长，默认 240 个逻辑像素；保持帧宽高比，在窗口中底部居中。仅影响显示，不改变 PNG 尺寸；可改为 512 等值，没有 48×48 限制。
- `pixelated`：默认 `true`，使用近邻缩放；`false` 使用平滑缩放。
- `facing`：原图面朝方向，`right` 或 `left`；反向移动时仅在显示中水平翻转。
- `movement.walk_speed` / `run_speed`：默认 75 / 300 逻辑像素每秒。
- `movement.duration_seconds`：自动动作持续时间范围；Run 另加一次完整扎针的时间。
- `clips.*.fps`：分别调整待机、行走、扎针、冲刺帧率。
- `clips.*.frames`：帧顺序，可重复帧号实现某个姿势停留更久。
- `sheets.*.file`：相对配置文件目录的 PNG 路径；可为扎针单独指定一张图。
- `sheets.*.columns` / `rows`：均匀网格。非均匀排版可替换为 `rects: [[x,y,width,height], ...]`，每个矩形对应一帧。
- `sheets.*.canvas`：可选的统一原始帧画布 `[宽, 高]`，不得小于任一取帧矩形；帧在画布内底部居中，不缩放角色内容。

当前 PNG 自带透明通道，程序直接使用。低透明度残留、原有特效、帧间姿势和清晰度均由原素材决定；本程序不会生成新的像素画或补帧。

## 占位测试、检查与打包

```powershell
# 几何块占位，不加载角色 PNG
.\.venv\Scripts\python.exe .\main.py --placeholder

# 检查图片、帧数、配置并退出
.\.venv\Scripts\python.exe .\main.py --check

# 实际桌面窗口运行 8 秒后自动关闭
.\.venv\Scripts\python.exe .\main.py --state run --smoke-test 8

# 状态机、边界、素材及窗口交互回归测试
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

# 打包 Windows 文件夹版 EXE
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

可用 `--config 路径` 指定另一份配置。运行不需要联网，不创建开机启动项。源代码分为 `pet/engine.py`（状态机与移动）、`pet/resources.py`（素材读取）、`pet/window.py`（桌面窗口），后续可独立扩展。

透明窗口遵循 [Qt 官方 QWidget 文档](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html) 的 Windows 无边框与透明背景要求。
