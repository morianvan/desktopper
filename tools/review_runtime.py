"""Native Windows integration review; uses the real event loop and paint path."""
import ctypes
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QTimer, QRect
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication
from pet.resources import Resources
from pet.window import PetWindow


def main():
    app = QApplication([])
    resources = Resources(ROOT / "assets/animations.json")
    window = PetWindow(resources)
    output = ROOT / "docs/review-v2.1"
    output.mkdir(parents=True, exist_ok=True)
    state_trace, snapshots, seen = [], [], []
    flags = {"jump_requested": False, "run_requested": False, "walk_requested": False, "scaled_in_air": False}
    failures = []
    started = time.monotonic()
    last_key = None

    def finish():
        sampler.stop()
        window.pause_action.setChecked(True)
        try:
            assert state_trace == ["knife", "idle", "jumppad", "idle", "stim", "run", "walk"], state_trace
            for name in ("knife", "jumppad", "stim"):
                positions = {row["position"] for row in seen if row["state"] == name}
                assert positions == set(range(len(resources.clips[name].frames))), (name, positions)
            assert flags["scaled_in_air"]
            # Screenshot the same actual window pose at three proportional sizes.
            sizes = []
            for percent in (50, 100, 200):
                window.set_scale_percent(percent, persist=False)
                window.repaint()
                app.processEvents()
                pixmap = window.grab()
                sizes.append((window.width(), pixmap))
            image = QImage(1040, 600, QImage.Format.Format_RGB32)
            image.fill(QColor("#283045"))
            painter = QPainter(image)
            x = 10
            for (percent, (size, pixmap)) in zip((50, 100, 200), sizes):
                painter.drawPixmap(QRect(x, 570 - size, size, size), pixmap, pixmap.rect())
                painter.setPen(QColor("white"))
                painter.drawText(x + 5, 590, f"{percent}% / {size}px")
                x += size + 20
            painter.end()
            image.save(str(output / "native-scaling.png"))
        except Exception as error:
            failures.append(str(error))
        report = {"states": state_trace, "flags": flags, "errors": failures, "sampled_frames": seen}
        (output / "native-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"states": state_trace, "flags": flags, "errors": failures, "samples": len(seen)}))
        # Exercise the actual menu's exit action.
        next(action for action in window.menu.actions() if action.text() == "退出").trigger()

    def sample():
        nonlocal last_key
        try:
            animator = window.behavior.animator
            if not state_trace or state_trace[-1] != animator.state:
                state_trace.append(animator.state)
            key = (animator.state, animator.frame_position)
            if key != last_key:
                seen.append({"time": round(time.monotonic() - started, 3), "state": key[0],
                             "position": key[1], "source_frame": resources.clips[key[0]].frames[key[1]]})
                # Capture important moments through QWidget's real painting path.
                if (key[0] == "jumppad" and key[1] in (5, 6, 7, 9, 11, 13, 17, 18, 19)):
                    window.grab().save(str(output / f"jump-{key[1]:02d}.png"))
                last_key = key
            if animator.state == "knife" and animator.elapsed > 0.4 and not flags["jump_requested"]:
                window.select_action("jumppad")
                flags["jump_requested"] = True
            if animator.state == "jumppad" and animator.frame_position == 6 and not flags["scaled_in_air"]:
                elapsed = animator.elapsed
                window.scale_actions[150].trigger()
                assert animator.elapsed == elapsed and animator.state == "jumppad"
                flags["scaled_in_air"] = True
                window.select_action("run")
                flags["run_requested"] = True
            if animator.state == "run" and animator.elapsed > 0.5 and sum(s["state"] == "run" for s in seen) > 24 and not flags["walk_requested"]:
                window.select_action("walk")
                flags["walk_requested"] = True
            if animator.state == "walk" and animator.elapsed > 0.3:
                finish()
            elif time.monotonic() - started > 20:
                raise AssertionError("Runtime review timed out")
        except Exception as error:
            failures.append(str(error))
            finish()

    window.select_action("knife")
    window.show()
    app.processEvents()
    if sys.platform == "win32":
        style = ctypes.windll.user32.GetWindowLongW(int(window.winId()), -20)
        assert style & 8 and style & 0x80000
    sampler = QTimer()
    sampler.timeout.connect(sample)
    sampler.start(8)
    app.exec()
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
