"""Create a portable Windows ZIP and SHA-256 checksum after build.ps1."""
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.1.0"


def main():
    folder = ROOT / "dist" / "Desktopper"
    if not (folder / "Desktopper.exe").is_file():
        raise SystemExit("Run build.ps1 first.")
    archive = ROOT / "dist" / f"Desktopper-{VERSION}-windows-x64.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.name not in {"user-settings.json", "user-settings.tmp"}:
                output.write(path, path.relative_to(folder.parent))
    hasher = hashlib.sha256()
    with archive.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    checksum = archive.with_suffix(".zip.sha256")
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    with zipfile.ZipFile(archive) as output:
        bad = output.testzip()
        if bad:
            raise SystemExit(f"ZIP integrity check failed: {bad}")
    print(f"{archive.name}: {archive.stat().st_size:,} bytes")
    print(f"SHA256 {digest}")


if __name__ == "__main__":
    main()
