"""Deterministic sprite export from the user's supplied V2 sheets.

No invented poses, interpolation, alpha cleanup, or source-file modification.
Run with the project's Python (requires only the existing PySide6 dependency).
"""
import hashlib
import json
from pathlib import Path
import sys
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "sources" / "v2"
OUTPUT = ROOT / "assets" / "v2"


def export():
    layout = json.loads((SOURCE / "layout.json").read_text(encoding="utf-8"))
    width, height = layout["canvas"]
    anchor_x, anchor_y = layout["anchor"]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report = {"version": 2, "canvas": [width, height], "anchor": [anchor_x, anchor_y],
              "processing": "crop, uniform per-sheet nearest-neighbor scale, anchor placement only",
              "sheets": {}}
    previews = {}
    for name, spec in layout["sheets"].items():
        path = SOURCE / spec["file"]
        original = QImage(str(path))
        if original.isNull() or not original.hasAlphaChannel():
            raise ValueError(f"{name}: missing or non-transparent source")
        count = (len(spec["y_edges"]) - 1) * 4
        sheet = QImage(width * 4, height * (count // 4), QImage.Format.Format_ARGB32)
        sheet.fill(Qt.GlobalColor.transparent)
        frames_dir = OUTPUT / "frames" / name
        frames_dir.mkdir(parents=True, exist_ok=True)
        frame_records = []
        previews[name] = []
        for index in range(count):
            row, col = divmod(index, 4)
            edges = spec.get("row_x_edges", [spec["x_edges"]] * (count // 4))[row]
            x, right = edges[col:col + 2]
            y, bottom = spec["y_edges"][row:row + 2]
            rect = QRect(x, y, right - x, bottom - y)
            if not original.rect().contains(rect):
                raise ValueError(f"{name} {index}: source rectangle out of bounds")
            center = spec.get("frame_centers", spec["centers"] * (count // 4))[index]
            ground = spec["ground"][row]
            piece = original.copy(rect)
            scaled = piece.scaled(round(piece.width() * spec["scale"]),
                                  round(piece.height() * spec["scale"]),
                                  Qt.AspectRatioMode.IgnoreAspectRatio,
                                  Qt.TransformationMode.FastTransformation)
            left = anchor_x - round((center - x) * spec["scale"])
            top = anchor_y - round((ground - y) * spec["scale"])
            if min(left, top) < 0 or left + scaled.width() > width or top + scaled.height() > height:
                raise ValueError(f"{name} {index}: normalized canvas would clip source rectangle")
            frame = QImage(width, height, QImage.Format.Format_ARGB32)
            frame.fill(Qt.GlobalColor.transparent)
            painter = QPainter(frame)
            painter.drawImage(left, top, scaled)
            painter.end()
            filename = f"{index:02d}.png"
            if not frame.save(str(frames_dir / filename)):
                raise OSError(f"Cannot export {name}/{filename}")
            sheet_painter = QPainter(sheet)
            sheet_painter.drawImage(col * width, row * height, frame)
            sheet_painter.end()
            frame_records.append({"index": index, "rect": [x, y, right - x, bottom - y],
                                  "source_anchor": [center, ground], "destination": [left, top]})
            previews[name].append(frame)
        if not sheet.save(str(OUTPUT / f"{name}.png")):
            raise OSError(f"Cannot export {name} atlas")
        report["sheets"][name] = {
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_size": [original.width(), original.height()],
            "frames": count, "scale": spec["scale"], "frame_details": frame_records,
        }
    (OUTPUT / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    # UI QA contact sheets use an opaque backing so alpha fringes are judged correctly.
    preview_dir = ROOT / "docs" / "v2-preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    for name, frames in previews.items():
        image = QImage(256 * 4, 280 * ((len(frames) + 3) // 4), QImage.Format.Format_RGB32)
        image.fill(QColor("#283045"))
        painter = QPainter(image)
        painter.setFont(QFont("Segoe UI", 10))
        for index, frame in enumerate(frames):
            col, row = index % 4, index // 4
            painter.drawImage(col * 256, row * 280, frame.scaled(256, 256))
            painter.setPen(QColor("#7e89a1"))
            painter.drawLine(col * 256, row * 280 + anchor_y // 2, col * 256 + 255, row * 280 + anchor_y // 2)
            painter.setPen(QColor("white"))
            painter.drawText(col * 256 + 10, row * 280 + 273, f"{name.upper()}  {index:02d}")
        painter.end()
        image.save(str(preview_dir / f"{name}.png"))
    print(json.dumps({name: spec["frames"] for name, spec in report["sheets"].items()}))


if __name__ == "__main__":
    app = QGuiApplication(sys.argv[:1])
    export()
