"""Back up both SQLite databases and uploaded files into a new directory.

Stop application writers before running for consistency across the two databases
and files. Individual SQLite snapshots use the online backup API.
"""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
try:
    from .backup_core import backup
except ImportError:
    from backup_core import backup


def bundle(root, destination):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    manifest = {"databases": [], "uploads": [], "requires_stopped_writers": True}
    for relative in ("data/core.db", "frontend/db.sqlite3"):
        source = root / relative
        if source.is_file():
            target = backup(source, destination / relative)
            manifest["databases"].append({"path": relative, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    with zipfile.ZipFile(destination / "uploads.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for relative in ("uploads", "frontend/media"):
            directory = root / relative
            if directory.is_dir():
                for path in directory.rglob("*"):
                    if path.is_file() and path.resolve().is_relative_to(directory.resolve()):
                        name = path.relative_to(root).as_posix()
                        archive.write(path, name)
                        manifest["uploads"].append(name)
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    args = parser.parse_args()
    print(bundle(args.root, args.destination))
