"""Utility for copying a set of files into ``~/Downloads/Sorted``.

The paths to copy are read from a text file.  Each non-empty line should be an
absolute path to a file.  The file names are preserved when copying.  Missing
files are reported but do not abort the script.
"""

from pathlib import Path, PureWindowsPath
import shutil


def copy_files(list_path: Path) -> None:
    """Copy files listed in ``list_path`` to ``~/Downloads/Sorted``."""
    target_dir = Path.home() / "Downloads" / "Sorted"
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"Target folder: {target_dir}")

    with list_path.open(encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue

            # Support Windows-style paths even when run from other platforms.
            source_path = Path(line)
            if not source_path.exists() and ("\\" in line or ":" in line):
                source_path = Path(PureWindowsPath(line))

            if source_path.exists():
                dest = target_dir / source_path.name
                shutil.copy2(source_path, dest)
                print(f"Copied {source_path} -> {dest}")
            else:
                print(f"Missing: {source_path}")


def main() -> None:
    # Prefer a list file in the current working directory.  Accept both
    # ``sorted-list.txt`` and ``download-list.txt`` for convenience.
    for name in ("sorted-list.txt", "download-list.txt"):
        candidate = Path(name)
        if candidate.exists():
            copy_files(candidate)
            return

    print("List file not found. Place 'sorted-list.txt' or 'download-list.txt' next to the script.")


if __name__ == "__main__":
    main()
