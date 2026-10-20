import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import unittest
import hashlib
import json
import tempfile
from PySide6.QtCore import Qt, QPointF, QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from pet.resources import Resources, load_config, slice_rects
from pet.window import PetWindow

ROOT = Path(__file__).resolve().parents[1]


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.resources = Resources(ROOT / "assets" / "animations.json")

    def setUp(self):
        self.window = PetWindow(self.resources)
        self.window.timer.stop()

    def tearDown(self):
        self.window.close()

    def test_assets_and_odd_grid_cover_whole_image(self):
        self.assertEqual(self.resources.sheet_info["run"], [2048, 2048, 16, True])
        self.assertEqual([len(self.resources.frames[k]) for k in ("idle", "walk", "stim", "run", "knife", "jumppad")],
                         [14, 12, 4, 12, 15, 20])
        rects = slice_rects({"columns": 4, "rows": 2}, 1774, 887)
        self.assertEqual(sum(w * h for x, y, w, h in rects), 1774 * 887)
        with self.assertRaises(ValueError):
            slice_rects({"rects": [[1770, 0, 10, 10]]}, 1774, 887)

    def test_window_flags_transparent_pixels_and_manual_run(self):
        window = self.window
        self.assertTrue(window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        self.assertTrue(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        window.select_action("run")
        self.assertFalse(window.behavior.auto)
        self.assertEqual(window.behavior.animator.state, "stim")
        window.behavior.advance(0.9)
        self.assertEqual(window.behavior.animator.state, "run")
        self.assertEqual(window.current_pixmap().toImage().pixelColor(0, 0).alpha(), 0)
        window.show()
        self.app.processEvents()
        self.assertFalse(window.grab().isNull())

    def test_drag_freezes_then_updates_position(self):
        window = self.window
        window.show()
        self.app.processEvents()
        initial = window.pos()
        local = QPointF(120, 120)
        start = QPointF(initial) + local
        press = QMouseEvent(QEvent.Type.MouseButtonPress, local, start,
                            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        window.mousePressEvent(press)
        self.assertTrue(window.dragging)
        elapsed = window.behavior.animator.elapsed
        window.tick()
        self.assertEqual(window.behavior.animator.elapsed, elapsed)
        move = QMouseEvent(QEvent.Type.MouseMove, local, start + QPointF(30, -30),
                           Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        window.mouseMoveEvent(move)
        self.assertEqual(window.pos().x(), initial.x() + 30)
        self.assertEqual(window.pos().y(), initial.y() - 30)
        release = QMouseEvent(QEvent.Type.MouseButtonRelease, local, start + QPointF(30, -30),
                              Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        window.mouseReleaseEvent(release)
        self.assertFalse(window.dragging)

    def test_menu_pause_and_exit_available(self):
        window = self.window
        window.pause_action.setChecked(True)
        elapsed = window.behavior.animator.elapsed
        window.tick()
        self.assertEqual(window.behavior.animator.elapsed, elapsed)
        window.pause_action.setChecked(False)
        window.menu.popup(window.pos())
        self.app.processEvents()
        self.assertTrue(window.menu_open)
        window.tick()
        self.assertEqual(window.behavior.animator.elapsed, elapsed)
        window.menu.hide()
        self.assertFalse(window.menu_open)
        self.assertIn("退出", [a.text() for a in window.menu.actions()])

    def test_placeholder_does_not_need_png_files(self):
        resources = Resources(ROOT / "assets" / "animations.json", placeholder=True)
        self.assertFalse(resources.frames["idle"][0].isNull())

    def test_v1_config_remains_usable(self):
        old = Resources(ROOT / "assets" / "animations-v1.json")
        self.assertEqual(len(old.frames["run"]), 4)
        self.assertNotIn("knife", old.frames)

    def test_all_exported_frames_have_same_canvas_and_source_hashes(self):
        from PySide6.QtGui import QImage
        manifest = json.loads((ROOT / "assets/v2/manifest.json").read_text())
        self.assertEqual(manifest["anchor"], [256, 464])
        for name, record in manifest["sheets"].items():
            source = ROOT / "assets/sources/v2" / f"{name}.png"
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), record["source_sha256"])
            frames = sorted((ROOT / "assets/v2/frames" / name).glob("*.png"))
            self.assertEqual(len(frames), record["frames"])
            hashes = set()
            for path in frames:
                image = QImage(str(path))
                self.assertEqual((image.width(), image.height()), (512, 512))
                self.assertTrue(image.hasAlphaChannel())
                self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
                hashes.add(hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(len(hashes), len(frames), "Do not pad frame counts with duplicates")

    def test_special_menu_actions_and_pause_during_special(self):
        window = self.window
        for state, label in (("knife", "蝴蝶刀"), ("jumppad", "跳板连跳")):
            window.behavior.animator._enter("idle")
            window.behavior.animator.settling = False
            action = next(a for a in window.menu.actions() if a.text().startswith(label))
            action.trigger()
            self.assertEqual(window.behavior.animator.state, state)
            window.pause_action.setChecked(True)
            window.tick()
            self.assertEqual(window.behavior.animator.elapsed, 0)
            window.pause_action.setChecked(False)
            window.behavior.advance(window.resources.clips[state].duration + 0.01)
            self.assertEqual(window.behavior.animator.state, "idle")
            self.assertFalse(window.auto_action.isChecked())

    def test_scaling_preserves_foot_anchor_and_animation_time(self):
        window = self.window
        window.x_float, window.y_float = 200, 100
        window.move(200, 100)
        window.select_action("jumppad")
        window.behavior.advance(0.6)
        elapsed = window.behavior.animator.elapsed
        foot_x = window.x_float + window.width() / 2
        foot_y = window.y_float + window.height() * 464 / 512
        window.set_scale_percent(125)
        self.assertEqual(window.width(), window.height())
        self.assertEqual(window.width(), 350)
        self.assertAlmostEqual(window.x_float + window.width() / 2, foot_x)
        self.assertAlmostEqual(window.y_float + window.height() * 464 / 512, foot_y)
        self.assertEqual(window.behavior.animator.elapsed, elapsed)
        self.assertEqual(window.behavior.animator.state, "jumppad")
        self.assertEqual(window.current_pixmap().width(), 512, "Scale from full-resolution source")

    def test_scaling_clamps_to_screen_at_corners(self):
        window = self.window
        left, top, right, bottom = window.bounds()
        for x, y in ((left, top), (right, bottom)):
            window.x_float, window.y_float = x, y
            window.set_scale_percent(200)
            left2, top2, right2, bottom2 = window.bounds()
            self.assertGreaterEqual(window.x_float, left2)
            self.assertGreaterEqual(window.y_float, top2)
            self.assertLessEqual(window.x_float, right2)
            self.assertLessEqual(window.y_float, bottom2)
        window.set_scale_percent(-50)
        self.assertEqual(window.scale_percent, 50)

    def test_size_menu_and_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            window = PetWindow(self.resources, path)
            window.timer.stop()
            window.scale_actions[150].trigger()
            self.assertEqual(window.scale_percent, 150)
            self.assertEqual(json.loads(path.read_text())["scale_percent"], 150)
            window.close()
            restored = PetWindow(self.resources, path)
            restored.timer.stop()
            self.assertEqual(restored.scale_percent, 150)
            self.assertEqual(restored.width(), 420)
            restored.close()

    def test_corrected_choreography_retains_pad_and_returns_prop(self):
        jump = self.resources.clips["jumppad"]
        self.assertNotIn(8, jump.frames, "Skip the original frame with a missing pad")
        self.assertEqual(jump.frames[-3:], (2, 1, 0), "Step off and retrieve the pad before idle")
        knife = self.resources.clips["knife"]
        self.assertEqual(knife.frames[-3:], (13, 14, 15))
        self.assertTrue({6, 8, 12}.isdisjoint(knife.frames), "Skip wide overhead swings")

    def test_invalid_special_and_transition_cycle_are_rejected(self):
        config = json.loads((ROOT / "assets/animations.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            config["clips"]["knife"]["fps"] = 0
            path.write_text(json.dumps(config))
            with self.assertRaises(ValueError):
                load_config(path)
            config["clips"]["knife"]["fps"] = 9
            config["clips"]["idle"]["next"] = "knife"
            path.write_text(json.dumps(config))
            with self.assertRaises(ValueError):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
