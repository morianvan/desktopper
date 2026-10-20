# Octane「蜘蛛热」Windows 桌宠 V2

Python + PySide6 原生桌宠。按用户确认，直接接入提供的五张动作图，保留现有角色、刀刃、跳板和动作姿势，不重新生成角色，不重绘，不补入重复帧，不使用交叉淡化伪装补帧。

## 启动和操作

双击 `dist\OctaneDesktopPetV2\OctaneDesktopPetV2.exe`。它是 Windows x64 文件夹版应用，不需要安装 Python；移动到其他电脑时复制整个 `OctaneDesktopPetV2` 文件夹，包括 `_internal` 和 `assets`。

源码启动仍为 `launch.bat`。首次需要 Python 3.10+ x64，或者本机 Codex 附带的 Python；安装依赖见 `setup.ps1`。

- 左键拖动角色，松开继续；可以拖到另一块屏幕。
- 右键角色或托盘图标：待机、行走、扎针后冲刺、蝴蝶刀、跳板连跳、自动动作、暂停、退出。
- 手动选择动作会关闭自动切换。KNIFE/JUMPPAD 播完后回到 IDLE，保持待机；重新勾选自动切换即可恢复随机活动。
- 自动模式也可能选中蝴蝶刀和跳板。单次动作完整播放后，先在 IDLE 停留 3～7 秒，再随机选择。
- 拖拽、暂停、打开菜单都会冻结动画和移动；不会在后台跳过帧。手动选另一个动作可以主动打断当前动作。
- 当前显示器工作区内自动移动，边缘转向，避开任务栏。透明背景、窗口置顶。

## V2 动作

| 动作 | 真实帧数 | 默认帧率 | 播放方式 |
|---|---:|---:|---|
| IDLE | 12 | 8 fps | 循环，包含蹲起、挑衅手势和亢奋姿态 |
| WALK | 12 | 14 fps | 小碎步循环 |
| STIM | 4 | 6 fps | 每次进入 RUN 时播放一次 |
| SPRINT / RUN | 12 | 20 fps | 扎针结束后高速移动并循环；与 STIM 合计 16 帧 |
| KNIFE | 16 | 9 fps | 完整播放一次后回 IDLE |
| JUMPPAD | 16 | 8 fps | 放跳板、踩踏、弹起、连续弹跳、落地，播完回 IDLE |

再次选择正在播放的 RUN 不会重新扎针；离开后再进入才会扎针。STIM、KNIFE、JUMPPAD 期间窗口原地停留，跳跃高度由提供的动画表现。跳板不会作为独立对象残留在桌面。

## 素材交付

- `assets/sources/v2/`：五张用户原图的逐字节副本，未覆盖或修改。
- `assets/sources/v2/layout.json`：原图取帧区域、缩放比例与落脚锚点。
- `assets/v2/frames/<动作>/00.png` 等：**72 张独立 RGBA PNG，每帧 512×512**。
- `assets/v2/idle.png`、`walk.png`：4×3 图集，2048×1536。
- `assets/v2/run.png`、`knife.png`、`jumppad.png`：4×4 图集，2048×2048。
- `assets/v2/manifest.json`：原图 SHA256、尺寸、每帧源矩形、锚点和缩放记录。
- `docs/v2-preview/`：带基准线的逐帧检查图；背景仅用于预览，正式 PNG 保持透明。

所有帧统一锚点为 **(256, 464)**；各组使用固定等比缩放，调整站立角色的显示尺寸，保留原图的头身比例及蹲伏变化。跳板以地面/跳板底部为锚点，腾空帧不会被错误拉回地面。没有插入额外动作或 AI 补帧；这次新图本身已满足所需帧数。

素材本身的角色细节和姿势差异保留。Run 原图有特效跨越相邻帧，分帧后可能残留边缘碎光；未进行抹除或重绘。跳板第 9 帧（编号 08）原图没有跳板，导出也照原样保留。画布与坐标已统一，但不宣称对原画做了逐像素重绘或骨骼校正。

## 配置与替换

配置位于 `assets/animations.json`，打包后修改 EXE 同目录中的这份文件，重启生效。

- `display_height`：显示画布边长，默认 280 个逻辑像素；原始导出尺寸保持 512×512。
- `pixelated`：`true` 使用近邻缩放；`false` 使用平滑缩放。
- `clips.<动作>.fps`：调整动作速度。
- `clips.<动作>.frames`：从 0 开始、从左到右、从上到下的帧号。
- `clips.stim.next` 固定为 `run`；`clips.knife.next`、`clips.jumppad.next` 固定为 `idle`。不设置 `next` 的普通动作循环播放。
- `movement.walk_speed` / `run_speed`：默认 75 / 300 逻辑像素每秒。
- `movement.duration_seconds`：自动切换的等待时间范围。
- `movement.action_weights`：随机选择时的相对权重；数值越大越常出现，必须为正数。
- `sheets`：替换图集路径和行列数。仍兼容 V1 的自定义 `rects` 与 `canvas` 配置。

`assets/animations-v1.json` 及 V1 原图仍保留；新程序可以通过 `--config assets/animations-v1.json` 使用旧素材。旧 EXE 位于原来的 `dist/OctaneDesktopPet/`。

## 开发与验证

```powershell
# 素材检查
.\.venv\Scripts\python.exe main.py --check

# 指定动作；单次动作之后会自动回 Idle
.\.venv\Scripts\python.exe main.py --state KNIFE
.\.venv\Scripts\python.exe main.py --state JUMPPAD

# 无素材占位测试
.\.venv\Scripts\python.exe main.py --placeholder

# 由保留的原图和布局重新导出透明 PNG（无需联网）
.\.venv\Scripts\python.exe tools\prepare_v2_assets.py

# 回归测试
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

# 原生桌面运行 5 秒后自动退出
.\.venv\Scripts\python.exe main.py --state jumppad --smoke-test 5

# 打包 V2
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

素材导出只使用 Qt 的裁切、整组等比缩放和透明画布绘制，源图不变。程序结构为 `pet/engine.py`（状态机）、`pet/resources.py`（配置与加载）、`pet/window.py`（窗口与菜单）。无开机启动、网络请求或社区上传。
