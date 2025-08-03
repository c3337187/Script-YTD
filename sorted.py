from pathlib import Path
import shutil

def copy_files(list_path: Path) -> None:
    """Copy files listed in ``list_path`` to ``~/Downloads/Sorted``.

    Each line in ``list_path`` should contain an absolute path to a file. The
    file names are preserved when copying. Missing files are skipped.
    """
    if not list_path.exists():
        raise FileNotFoundError(f"List file not found: {list_path}")

    target_dir = Path.home() / "Downloads" / "Sorted"
    target_dir.mkdir(parents=True, exist_ok=True)

    with list_path.open(encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            source_path = Path(line)
            if source_path.exists():
                dest = target_dir / source_path.name
                shutil.copy2(source_path, dest)
            else:
                print(f"Missing: {source_path}")

def main() -> None:
    script_dir = Path(__file__).resolve().parent
    list_file = script_dir / "download-list.txt"
    copy_files(list_file)

if __name__ == "__main__":
    main()
