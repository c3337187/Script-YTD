# Script-YTD

This repository contains a helper script for downloading media from the
clipboard on Windows. The `main_windows_strict.py` script places an icon in the
system tray and reacts to global hotkeys.

## Repository layout

- `main_windows_strict.py` – main application script
- `requirements.txt` – list of required Python packages such as
  `yt-dlp`, `requests`, `beautifulsoup4`, `keyboard`, `pystray`,
  `pyperclip`, `pillow`, `pyinstaller`, and `pywin32`
- `build.py` – installs missing packages and builds an executable
- `icons/` – tray icons used by the application
- `system/` – configuration, logs and build output

## Quick start

1. Install Python 3.10 or newer.
2. Run `python build.py`.
   The script installs required packages and builds an executable in `system/`.
3. Launch the generated `.exe` from the `system` directory.

## Manual commands

Install dependencies manually:

```bash
pip install -r requirements.txt
```

Build the executable manually with PyInstaller:

```bash
pyinstaller --noconsole --onefile --icon icons/ico.ico \
  --add-data "icons;icons" --add-data "system;system" \
  --distpath system main_windows_strict.py
```

The icons folder contains three images used in the tray:
`ico.ico` (default), `act.ico` (active) and `dw.ico` (downloading).

## Runtime files

The first launch creates a `Downloads/` directory with these subfolders:

- `Videos/` – YouTube videos
- `Videos/Playlist Videos/` – playlist items
- `Pictures/` – single images
- `Pictures/Wildberries/` – Wildberries product images

All runtime files (config, logs and download list) are stored in the `system/` folder.
