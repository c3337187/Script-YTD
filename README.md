# Script-YTD

This repository contains a helper script for downloading media from the
clipboard on Windows. The `main_windows_strict.py` script places an icon in the
system tray and reacts to global hotkeys. Clipboard actions are handled in a
small helper process so the hotkey works reliably. The helper retries clipboard
operations several times to ensure links are captured.

## Repository layout

- `main_windows_strict.py` – main application script
- `requirements.txt` – list of required Python packages such as
  `yt-dlp`, `requests`, `beautifulsoup4`, `keyboard`, `pystray`,
  `pyperclip`, `pillow`, `pyinstaller`, and `pywin32`
- `build.py` – installs missing packages and builds an executable
- `icons/` – tray icons used by the application
- `system/` – configuration and logs

## Quick start

1. Install Python 3.10 or newer.
2. Run `python build.py`.
   The script installs required packages and builds an executable in the project root.
3. Launch the generated `.exe` from the repository directory.

## Manual commands

Install dependencies manually:

```bash
pip install -r requirements.txt
```

Build the executable manually with PyInstaller:

```bash
pyinstaller --noconsole --onefile --icon icons/ico.ico \
  --add-data "icons;icons" \
  --distpath . main_windows_strict.py
```

The icons folder contains three images used in the tray:
`ico.ico` (default), `act.ico` (active) and `dw.ico` (downloading).

## Runtime files

The first launch creates a `Downloads/` directory with these subfolders:

- `Videos/` – YouTube videos
- `Videos/Playlist Videos/` – playlist items
- `Pictures/` – single images
- `Pictures/Wildberries/` – Wildberries product images

All runtime files (config, logs and the download list) are stored in the `system/` folder next to the executable.
