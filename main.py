import argparse
import json
from pathlib import Path
import sys
import traceback


def base_directory():
    # Assets live next to the executable, so users can replace them after packaging.
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="Desktopper · Windows 桌宠")
    parser.add_argument("--config", type=Path, help="角色包动画配置文件；省略时使用内置 Octane")
    parser.add_argument("--placeholder", action="store_true", help="使用带文字的几何占位块")
    parser.add_argument("--check", action="store_true", help="检查素材与配置后退出")
    parser.add_argument("--smoke-test", type=float, metavar="SECONDS", help="运行指定秒数后退出")
    parser.add_argument("--state", type=str.lower, choices=["idle", "walk", "run", "knife", "jumppad"],
                        help="启动动作；knife/jumppad 播完回到 idle")
    args = parser.parse_args()
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox
    from pet.resources import Resources
    from pet.window import PetWindow
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Desktopper")
    app.setQuitOnLastWindowClosed(True)
    try:
        resources = Resources(args.config or base_directory() / "assets" / "animations.json", args.placeholder)
        if args.check:
            report = json.dumps({"sheets": resources.sheet_info, "clips": {
                name: len(frames) for name, frames in resources.frames.items()}}, ensure_ascii=False, indent=2)
            if sys.stdout:
                print(report)
            return 0
        window = PetWindow(resources, base_directory() / "user-settings.json")
        if args.state:
            window.select_action(args.state)
        window.show()
        if args.smoke_test is not None:
            QTimer.singleShot(max(1, int(args.smoke_test * 1000)), app.quit)
        return app.exec()
    except Exception as error:
        if sys.stderr:
            traceback.print_exc()
        if not args.check:
            QMessageBox.critical(None, "桌宠启动失败", str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
