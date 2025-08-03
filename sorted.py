from pathlib import Path
import re
import shutil

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


def is_original(file_path: Path) -> bool:
    """Return True if ``file_path`` looks like an original image."""
    if file_path.suffix.lower() not in IMAGE_EXTENSIONS:
        return False
    stem = file_path.stem
    if stem.endswith("-scaled"):
        return False
    if re.search(r"-\d+x\d+$", stem):
        return False
    return True


def gather_images(list_path: Path, target_dir: Path) -> None:
    """Copy original images from directories listed in ``list_path`` to ``target_dir``."""
    if not list_path.exists():
        raise FileNotFoundError(f"List file not found: {list_path}")

    target_dir.mkdir(parents=True, exist_ok=True)

    with list_path.open(encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            base_dir = Path(line)
            if not base_dir.exists():
                print(f"Missing: {base_dir}")
                continue
            for file_path in base_dir.rglob("*"):
                if file_path.is_file() and is_original(file_path):
                    dest = target_dir / file_path.name
                    shutil.copy2(file_path, dest)


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    list_file = script_dir / "sorted-list.txt"
    target_dir = script_dir / "Sorted"
    gather_images(list_file, target_dir)


if __name__ == "__main__":
    main()
