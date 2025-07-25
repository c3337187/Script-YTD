import os
import subprocess
import sys

PACKAGES = {
    'yt_dlp': 'yt-dlp',
    'requests': 'requests',
    'bs4': 'beautifulsoup4',
    'keyboard': 'keyboard',
    'pystray': 'pystray',
    'pyperclip': 'pyperclip',
    'PIL': 'pillow',
    'PyInstaller': 'pyinstaller',
    'pywin32': 'pywin32',
}


def _module_exists(name: str) -> bool:
    from importlib.util import find_spec
    return find_spec(name) is not None


def ensure_packages() -> None:
    """Install required packages if they are missing."""
    for module, pkg in PACKAGES.items():
        if not _module_exists(module):
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg])


def create_runtime_dirs() -> None:
    """Prepare required directories and files for the build."""
    os.makedirs('system', exist_ok=True)
    os.makedirs('Downloads', exist_ok=True)
    videos = os.path.join('Downloads', 'Videos')
    playlists = os.path.join(videos, 'Playlist Videos')
    pictures = os.path.join('Downloads', 'Pictures')
    wb = os.path.join(pictures, 'Wildberries')
    for folder in (videos, playlists, pictures, wb):
        os.makedirs(folder, exist_ok=True)

    for filename in ('download-list.txt', 'config.ini', 'script.log', 'info.txt'):
        path = os.path.join('system', filename)
        if not os.path.exists(path):
            open(path, 'a', encoding='utf-8').close()


def build_exe() -> None:
    """Build executable using PyInstaller."""
    sep = ';' if sys.platform == 'win32' else ':'
    script = os.path.join(os.path.dirname(__file__), 'main_windows_strict.py')
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--noconsole',
        '--onefile',
        '--icon', 'icons/ico.ico',
        '--add-data', f'icons{sep}icons',
        '--workpath', 'build',
        '--distpath', 'system',
        script,
    ]
    subprocess.check_call(cmd)


if __name__ == '__main__':
    ensure_packages()
    create_runtime_dirs()
    build_exe()
