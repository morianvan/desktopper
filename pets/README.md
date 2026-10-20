# 添加其他桌宠

每个新角色使用独立目录，例如 `pets/my-pet/`，其中放置 `animations.json` 和 PNG 动画素材。
内置 Octane 仍在 `assets/`，不会因新增角色而被覆盖。

1. 将 `assets/animations.json` 复制到新角色目录。
2. 修改 `name` 为新角色名称，修改 `sheets` 中的文件路径、行列数和 `clips` 的帧序列。
3. 配置中的图片路径相对于该 JSON 文件所在目录解析。
4. 调整 `display_height`、`durations_ms`、移动速度和自动动作权重。
5. 检查并启动：

```powershell
# 源码版
.\.venv\Scripts\python.exe main.py --config pets\my-pet\animations.json --check
.\.venv\Scripts\python.exe main.py --config pets\my-pet\animations.json

# EXE 版（在 EXE 所在目录运行）
.\Desktopper.exe --config pets\my-pet\animations.json
```

也可以建立 Windows 快捷方式，在“目标”末尾添加 `--config "角色配置的绝对路径"`。

当前引擎必需 `idle`、`walk`、`stim`、`run`；`knife` 和 `jumppad` 可选。
没有扎针动作的新角色可以用一张准备姿势作为 `stim`，并配置 `next: "run"`。
删除可选动作时，也要从 `movement.action_weights` 中删除对应项。
尚不支持在运行中切换角色；不同角色可通过上述启动参数分别运行。

建议角色包采用透明 PNG，同一包内使用相同画布与脚底基线。当前默认缩放锚点为画布高度的 `464/512`，统一素材时沿用该基线可以避免调整尺寸时脚底移动。原图像素不必压缩到 48×48。

引擎会按配置切帧并缓存，PNG 原文件不会被重绘；图片本身的缺帧和跨格特效需要在素材制作阶段处理。新增角色前请确认素材来源及允许的使用范围。
