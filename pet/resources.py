"""Read-only sprite slicing. No source PNG is modified."""
import json
import math
from pathlib import Path
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from .engine import ACTIONS, DEFAULT_NEXT, Clip


def positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} 必须为正数")
    return value


def load_config(path: Path):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    height = data["display_height"]
    if not isinstance(height, int) or not 64 <= height <= 1024:
        raise ValueError("display_height 必须是 64～1024 的整数")
    if data.get("facing", "right") not in ("right", "left"):
        raise ValueError("facing 必须是 right 或 left")
    movement = data["movement"]
    for key in ("walk_speed", "run_speed"):
        positive(movement[key], key)
    positive(movement.get("acceleration", 900), "acceleration")
    durations = movement["duration_seconds"]
    if len(durations) != 2 or positive(durations[0], "duration") > positive(durations[1], "duration"):
        raise ValueError("duration_seconds 必须为 [最短秒数, 最长秒数]")
    for name in ("idle", "walk", "stim", "run"):
        if name not in data["clips"]:
            raise ValueError(f"缺少必要动画：{name}")
    for name, clip in data["clips"].items():
        positive(clip["fps"], f"{name}.fps")
        if not clip["frames"] or any(type(f) is not int or f < 0 for f in clip["frames"]):
            raise ValueError(f"{name}.frames 必须是非负整数列表")
        if clip["sheet"] not in data["sheets"]:
            raise ValueError(f"{name} 引用了不存在的 sheet")
        durations = clip.get("durations_ms", [])
        if durations:
            if len(durations) != len(clip["frames"]):
                raise ValueError(f"{name}.durations_ms 必须与 frames 等长")
            for duration in durations:
                positive(duration, f"{name}.durations_ms")
        loop_start = clip.get("loop_start", 0)
        if type(loop_start) is not int or not 0 <= loop_start < len(clip["frames"]):
            raise ValueError(f"{name}.loop_start 越界")
        if any(type(index) is not int or not 0 <= index < len(clip["frames"])
               for index in clip.get("exit_frames", [])):
            raise ValueError(f"{name}.exit_frames 越界")
        successor = clip.get("next", DEFAULT_NEXT.get(name))
        if successor is not None and successor not in data["clips"]:
            raise ValueError(f"{name}.next 引用了不存在的动画：{successor}")
        if name in DEFAULT_NEXT and successor != DEFAULT_NEXT[name]:
            raise ValueError(f"{name}.next 必须为 {DEFAULT_NEXT[name]}")
    # Cycles of one-shot clips would skip idle or hang on large time steps.
    for start in data["clips"]:
        seen = set()
        current = start
        while current is not None:
            if current in seen:
                raise ValueError("单次动画的 next 不得形成循环")
            seen.add(current)
            current = data["clips"][current].get("next", DEFAULT_NEXT.get(current))
    for name, weight in movement.get("action_weights", {}).items():
        if name not in ACTIONS:
            raise ValueError(f"未知随机动作：{name}")
        positive(weight, f"action_weights.{name}")
    return data


def slice_rects(spec, width, height):
    if "rects" in spec:
        rects = spec["rects"]
    else:
        cols, rows = spec["columns"], spec["rows"]
        if type(cols) is not int or type(rows) is not int or cols <= 0 or rows <= 0:
            raise ValueError("columns 和 rows 必须为正整数")
        # Integer boundaries cover odd-sized sheets without truncating their outer edge.
        rects = [
            [c * width // cols, r * height // rows,
             (c + 1) * width // cols - c * width // cols,
             (r + 1) * height // rows - r * height // rows]
            for r in range(rows) for c in range(cols)
        ]
    for rect in rects:
        if len(rect) != 4 or any(type(n) is not int for n in rect):
            raise ValueError("rects 中每项必须为 [x, y, width, height] 整数")
        x, y, w, h = rect
        if min(x, y) < 0 or min(w, h) <= 0 or x + w > width or y + h > height:
            raise ValueError(f"精灵帧越界: {rect}, 图片 {width}×{height}")
    if not rects:
        raise ValueError("精灵图没有帧")
    return rects


class Resources:
    def __init__(self, path, placeholder=False):
        self.config = load_config(path)
        self.clips = {
            name: Clip(tuple(spec["frames"]), spec["fps"], spec.get("next", DEFAULT_NEXT.get(name)),
                       tuple(spec.get("durations_ms", [])), spec.get("loop_start", 0),
                       tuple(spec.get("exit_frames", [])))
            for name, spec in self.config["clips"].items()
        }
        # Preserve source detail. The window scales these originals at paint time.
        height = 512
        raw = {}
        self.sheet_info = {}
        for name, spec in self.config["sheets"].items():
            if placeholder:
                continue
            file = path.parent / spec["file"]
            image = QImage(str(file))
            if image.isNull():
                raise ValueError(f"无法读取素材：{file}；可使用 --placeholder 测试框架")
            rects = slice_rects(spec, image.width(), image.height())
            pieces = [image.copy(QRect(*rect)) for rect in rects]
            if "canvas" in spec:
                canvas = spec["canvas"]
                if len(canvas) != 2 or any(type(v) is not int or v <= 0 for v in canvas):
                    raise ValueError(f"{name}.canvas 必须是 [宽, 高] 正整数")
                if any(p.width() > canvas[0] or p.height() > canvas[1] for p in pieces):
                    raise ValueError(f"{name}.canvas 小于取帧矩形")
                aligned = []
                for piece in pieces:
                    frame = QImage(*canvas, QImage.Format.Format_ARGB32_Premultiplied)
                    frame.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(frame)
                    painter.drawImage((canvas[0] - piece.width()) // 2, canvas[1] - piece.height(), piece)
                    painter.end()
                    aligned.append(frame)
                pieces = aligned
            raw[name] = pieces
            self.sheet_info[name] = [image.width(), image.height(), len(rects), image.hasAlphaChannel()]
        self.frames = {}
        transform = Qt.TransformationMode.FastTransformation if self.config.get("pixelated", True) else Qt.TransformationMode.SmoothTransformation
        # Consistent canvas size; aspect ratio is preserved. PNG files remain untouched.
        for name, spec in self.config["clips"].items():
            frames = []
            for index in spec["frames"]:
                if placeholder:
                    pix = self._placeholder(height, name, index)
                else:
                    sheet = raw[spec["sheet"]]
                    if index >= len(sheet):
                        raise ValueError(f"{name} 的帧 {index} 超出素材帧数 {len(sheet)}")
                    source = QPixmap.fromImage(sheet[index])
                    scaled = source.scaled(height, height, Qt.AspectRatioMode.KeepAspectRatio, transform)
                    pix = QPixmap(height, height)
                    pix.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(pix)
                    painter.drawPixmap((height - scaled.width()) // 2, height - scaled.height(), scaled)
                    painter.end()
                frames.append(pix)
            self.frames[name] = frames
        self.mirrored = {
            name: [QPixmap.fromImage(p.toImage().mirrored(True, False)) for p in frames]
            for name, frames in self.frames.items()
        }

    @staticmethod
    def _placeholder(size, name, index):
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setBrush(QColor("#6555ae"))
        painter.setPen(QColor("#dcd6ff"))
        offset = (index % 2) * 4
        painter.drawRoundedRect(30, 35 + offset, size - 60, size - 70, 16, 16)
        painter.setFont(QFont("Segoe UI", max(8, size // 16)))
        painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, f"TEST\n{name.upper()}\n{index + 1}")
        painter.end()
        return pix
