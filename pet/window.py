import time
import json
from pathlib import Path
from PySide6.QtCore import Qt, QPoint, QRect, QTimer
from PySide6.QtGui import QAction, QActionGroup, QCursor, QIcon, QPainter
from PySide6.QtWidgets import QApplication, QWidget, QMenu, QSystemTrayIcon, QInputDialog
from .engine import Behavior, bounded_motion


class PetWindow(QWidget):
    def __init__(self, resources, settings_path=None):
        super().__init__()
        self.resources = resources
        self.behavior = Behavior(resources.clips, resources.config["movement"])
        self.paused = False
        self.dragging = False
        self.menu_open = False
        self.resizing = False
        self.settings_path = Path(settings_path) if settings_path else None
        self.base_size = resources.config["display_height"]
        self.scale_percent = 100
        self.drag_offset = QPoint()
        self.pet_name = resources.config.get("name", "Desktopper")
        self.setWindowTitle(f"{self.pet_name} · Desktopper")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(resources.config["display_height"], resources.config["display_height"])
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("左键拖动 · 右键切换动作或退出")
        self.active_screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        area = self.active_screen.availableGeometry()
        self.x_float = float(area.center().x() - self.width() // 2)
        self.y_float = float(area.bottom() - self.height() - 40)
        self._clamp()
        self.move(round(self.x_float), round(self.y_float))
        self.menu = self._make_menu()
        if self.settings_path and self.settings_path.exists():
            try:
                value = json.loads(self.settings_path.read_text(encoding="utf-8")).get("scale_percent", 100)
                if type(value) in (int, float):
                    self.set_scale_percent(int(value), persist=False)
            except (OSError, ValueError, OverflowError):
                pass
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(QIcon(resources.frames["idle"][0]), self)
            self.tray.setToolTip(f"{self.pet_name} · 右键管理")
            self.tray.setContextMenu(self.menu)
            self.tray.show()
        self.last_tick = time.monotonic()
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)
        QApplication.instance().screenRemoved.connect(self._screen_removed)

    def _make_menu(self):
        menu = QMenu(self)
        title = menu.addAction(self.pet_name)
        title.setEnabled(False)
        menu.addSeparator()
        self.auto_action = QAction("自动切换动作", menu, checkable=True, checked=True)
        self.auto_action.toggled.connect(self._toggle_auto)
        menu.addAction(self.auto_action)
        for label, state in [
            ("待机 Idle", "idle"), ("行走 Walk", "walk"), ("扎针 → 冲刺 Run", "run"),
            ("蝴蝶刀 Knife · 单次", "knife"), ("跳板连跳 Jump Pad · 单次", "jumppad"),
        ]:
            if state not in self.resources.clips:
                continue
            action = menu.addAction(label)
            action.triggered.connect(lambda checked=False, s=state: self.select_action(s))
        self.pause_action = QAction("暂停", menu, checkable=True)
        self.pause_action.toggled.connect(self._set_paused)
        menu.addAction(self.pause_action)
        size_menu = menu.addMenu("大小（等比缩放）")
        group = QActionGroup(size_menu)
        group.setExclusive(True)
        self.scale_actions = {}
        for percent in (50, 75, 100, 125, 150, 200):
            action = QAction(f"{percent}%", size_menu, checkable=True, checked=percent == 100)
            group.addAction(action)
            size_menu.addAction(action)
            action.triggered.connect(lambda checked=False, value=percent: self.set_scale_percent(value))
            self.scale_actions[percent] = action
        size_menu.addSeparator()
        self.custom_size_action = size_menu.addAction("自定义比例…")
        self.custom_size_action.triggered.connect(self._custom_size)
        menu.addSeparator()
        menu.addAction("退出").triggered.connect(QApplication.instance().quit)
        menu.aboutToShow.connect(lambda: self._set_menu_open(True))
        menu.aboutToHide.connect(lambda: self._set_menu_open(False))
        return menu

    def set_scale_percent(self, percent, persist=True):
        percent = max(50, min(200, int(percent)))
        area = self.active_screen.availableGeometry()
        new_size = min(round(self.base_size * percent / 100), area.width(), area.height())
        foot_ratio = 464 / 512
        foot_x = self.x_float + self.width() / 2
        foot_y = self.y_float + self.height() * foot_ratio
        self.setFixedSize(new_size, new_size)
        self.scale_percent = round(100 * new_size / self.base_size)
        self.x_float, self.y_float = foot_x - new_size / 2, foot_y - new_size * foot_ratio
        self._clamp()
        self.move(round(self.x_float), round(self.y_float))
        for value, action in self.scale_actions.items():
            action.setChecked(value == self.scale_percent)
        self.custom_size_action.setText(f"自定义比例…（当前 {self.scale_percent}%）")
        self.update()
        if persist and self.settings_path:
            try:
                temp = self.settings_path.with_suffix(".tmp")
                temp.write_text(json.dumps({"scale_percent": self.scale_percent}), encoding="utf-8")
                temp.replace(self.settings_path)
            except OSError:
                self.setToolTip("大小已调整；当前目录无法保存设置。")

    def _custom_size(self):
        self.resizing = True
        try:
            value, accepted = QInputDialog.getInt(self, "桌宠大小", "等比缩放（50%～200%）：",
                                                 self.scale_percent, 50, 200, 5)
            if accepted:
                self.set_scale_percent(value)
        finally:
            self.resizing = False
            self.last_tick = time.monotonic()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.angleDelta().y():
            self.set_scale_percent(self.scale_percent + (5 if event.angleDelta().y() > 0 else -5))
            event.accept()
        else:
            super().wheelEvent(event)

    def _set_menu_open(self, value):
        self.menu_open = value
        self.last_tick = time.monotonic()

    def _set_paused(self, value):
        self.paused = value

    def _toggle_auto(self, value):
        self.behavior.auto = value
        self.behavior.remaining = self.behavior._duration()

    def select_action(self, action):
        self.auto_action.setChecked(False)
        self.pause_action.setChecked(False)
        self.behavior.choose(action)
        self.update()

    def bounds(self):
        if self.active_screen not in QApplication.screens():
            self.active_screen = QApplication.primaryScreen()
        area = self.active_screen.availableGeometry()
        return (area.x(), area.y(), area.x() + area.width() - self.width(),
                area.y() + area.height() - self.height())

    def _clamp(self):
        self.x_float, self.y_float, self.behavior.dx, self.behavior.dy = bounded_motion(
            self.x_float, self.y_float, self.behavior.dx, self.behavior.dy, 0, 0, self.bounds())

    def _screen_removed(self, screen):
        self.active_screen = QApplication.primaryScreen()
        self._clamp()
        self.move(round(self.x_float), round(self.y_float))

    def tick(self):
        now = time.monotonic()
        # Avoid teleporting after sleep or a temporarily blocked event loop.
        seconds = min(now - self.last_tick, 0.1)
        self.last_tick = now
        if self.paused or self.dragging or self.menu_open or self.resizing:
            return
        self.behavior.advance(seconds)
        self.x_float, self.y_float, self.behavior.dx, self.behavior.dy = bounded_motion(
            self.x_float, self.y_float, self.behavior.dx, self.behavior.dy,
            self.behavior.speed, seconds, self.bounds())
        self.move(round(self.x_float), round(self.y_float))
        animator = self.behavior.animator
        labels = {"idle": "待机", "walk": "行走", "stim": "扎针", "run": "冲刺",
                  "knife": "蝴蝶刀", "jumppad": "跳板"}
        next_label = f" · 接下来：{labels[animator.pending]}" if animator.pending else ""
        self.setToolTip(f"{labels[animator.state]}{next_label}\n左键拖拽 · 右键菜单 · Ctrl+滚轮缩放")
        self.update()

    def current_pixmap(self):
        animator = self.behavior.animator
        mirror = (self.behavior.dx < 0) != (self.resources.config.get("facing", "right") == "left")
        frames = self.resources.mirrored if mirror else self.resources.frames
        return frames[animator.state][animator.frame_position]

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,
                              not self.resources.config.get("pixelated", True))
        pixmap = self.current_pixmap()
        painter.drawPixmap(QRect(0, 0, self.width(), self.height()), pixmap, pixmap.rect())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_offset = event.globalPosition().toPoint() - self.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging:
            point = event.globalPosition().toPoint()
            self.active_screen = QApplication.screenAt(point) or self.active_screen
            target = point - self.drag_offset
            self.x_float, self.y_float = float(target.x()), float(target.y())
            self._clamp()
            self.move(round(self.x_float), round(self.y_float))
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.last_tick = time.monotonic()
            event.accept()

    def contextMenuEvent(self, event):
        self.menu.popup(event.globalPos())
        event.accept()

    def closeEvent(self, event):
        self.timer.stop()
        if self.tray:
            self.tray.hide()
        event.accept()
        QApplication.instance().quit()
