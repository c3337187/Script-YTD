import os
import sys
import atexit
import time
import configparser
import logging
from urllib.parse import urlparse
from typing import Optional
import re

import yt_dlp
import requests
from bs4 import BeautifulSoup
import keyboard
import pystray
import pyperclip
import threading
import multiprocessing
from multiprocessing.connection import Connection
try:
    import win32clipboard
    import win32con
    import win32api
    import win32gui
except Exception:
    win32clipboard = None  # type: ignore
    win32con = None  # type: ignore
    win32api = None  # type: ignore
    win32gui = None  # type: ignore

# Simple URL validation pattern used when grabbing the clipboard
URL_RE = re.compile(r'https?://\S+', re.IGNORECASE)

from PIL import Image
import subprocess



class HotkeyManager:
    """Global hotkey registration using win32 API when available."""

    def __init__(self) -> None:
        self._handles: list[int | str] = []
        self._ids: dict[int, callable] = {}
        self._counter = 1
        self._loop_thread: threading.Thread | None = None

    def _parse_win(self, combo: str) -> tuple[int, int] | None:
        if not win32con:
            return None
        mods = 0
        key = None
        for part in combo.lower().split('+'):
            if part == 'ctrl':
                mods |= win32con.MOD_CONTROL
            elif part == 'alt':
                mods |= win32con.MOD_ALT
            elif part == 'shift':
                mods |= win32con.MOD_SHIFT
            elif part == 'win':
                mods |= win32con.MOD_WIN
            else:
                key = part
        if key is None:
            return None
        vk = getattr(win32con, f'VK_{key.upper()}', None)
        if vk is None:
            if len(key) == 1:
                vk = ord(key.upper())
            else:
                return None
        return mods, vk

    def _run_loop(self) -> None:
        if not win32gui:
            return
        while True:
            msg = win32gui.GetMessage(None, 0, 0)
            if not msg:
                break
            if msg[1] == win32con.WM_HOTKEY:
                cb = self._ids.get(msg[2])
                if cb:
                    cb()
            win32gui.TranslateMessage(msg)
            win32gui.DispatchMessage(msg)

    def register(self, combo: str, callback) -> None:
        if os.name == 'nt' and win32api:
            parsed = self._parse_win(combo)
            if parsed:
                mods, vk = parsed
                hot_id = self._counter
                self._counter += 1
                try:
                    if win32api.RegisterHotKey(None, hot_id, mods, vk):
                        logging.info('Registered win32 hotkey: %s', combo)
                        self._ids[hot_id] = callback
                        if not self._loop_thread:
                            self._loop_thread = threading.Thread(target=self._run_loop, daemon=True)
                            self._loop_thread.start()
                        return
                except Exception as e:
                    logging.error('Win32 hotkey failed: %s', e)
        handle = keyboard.add_hotkey(combo, callback, suppress=True)
        logging.info('Registered keyboard hotkey: %s', combo)
        self._handles.append(handle)

    def unregister_all(self) -> None:
        if os.name == 'nt' and win32api:
            for hot_id in list(self._ids):
                try:
                    win32api.UnregisterHotKey(None, hot_id)
                except Exception:
                    pass
            self._ids.clear()
        for handle in self._handles:
            try:
                keyboard.remove_hotkey(handle)
            except Exception:
                pass
        self._handles.clear()

    def start_listener(self) -> None:
        pass

    def stop_listener(self) -> None:
        pass


hotkey_manager = HotkeyManager()


class ClipboardHelper:
    """Helper process to perform clipboard operations reliably."""

    def __init__(self) -> None:
        self._parent_conn, child_conn = multiprocessing.Pipe()
        self._process = multiprocessing.Process(
            target=self._run, args=(child_conn,), daemon=True
        )
        self._process.start()

    def _run(self, conn: Connection) -> None:
        while True:
            try:
                cmd = conn.recv()
            except EOFError:
                break
            if cmd == 'copy':
                result = attempt_copy_selected_text()
                conn.send(result)
            elif cmd == 'exit':
                break
        conn.close()

    def copy_selection(self) -> str:
        if not self._process.is_alive():
            return ''
        try:
            self._parent_conn.send('copy')
            return self._parent_conn.recv()
        except Exception:
            return ''

    def stop(self) -> None:
        if self._process.is_alive():
            try:
                self._parent_conn.send('exit')
            except Exception:
                pass
            self._process.join(timeout=1)


clipboard_helper: ClipboardHelper | None = None


def read_clipboard() -> str:
    """Return text from the clipboard using available methods."""
    text = ""
    if win32clipboard:
        for _ in range(3):
            try:
                win32clipboard.OpenClipboard()
                text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                break
            except Exception:
                time.sleep(0.05)
            finally:
                try:
                    win32clipboard.CloseClipboard()
                except Exception:
                    pass
    if not text:
        try:
            text = pyperclip.paste()
        except Exception as e:
            logging.error("Pyperclip error: %s", e)
    return text


def send_ctrl_c() -> None:
    """Simulate pressing ``Ctrl+C`` using the best available method."""
    if win32api and win32con:
        try:
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(ord('C'), 0, 0, 0)
            win32api.keybd_event(ord('C'), 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            return
        except Exception as e:
            logging.error('keybd_event failed: %s', e)
    try:
        keyboard.press_and_release('ctrl+c')
    except Exception as e:
        logging.error('keyboard send failed: %s', e)


def copy_selected_text(timeout: float = 3.0) -> str:
    """Send ``Ctrl+C`` and return clipboard text once it updates."""
    before = read_clipboard()
    send_ctrl_c()
    # allow the system to update the clipboard
    time.sleep(0.2)
    end = time.time() + timeout
    while time.time() < end:
        text = read_clipboard()
        if text and text != before:
            return text
        time.sleep(0.4)
    return ''


def attempt_copy_selected_text(retries: int = 3, delay: float = 0.3) -> str:
    """Try ``copy_selected_text`` several times before giving up."""
    for _ in range(retries):
        text = copy_selected_text()
        if text:
            return text
        time.sleep(delay)
    return ''

def get_root_dir() -> str:
    """Return the distribution root directory."""
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        if os.path.basename(exe_dir) == 'system':
            return os.path.dirname(exe_dir)
        return exe_dir
    folder = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(folder) if os.path.basename(folder) == 'scripts' else folder


def resource_path(*parts: str) -> str:
    """Resolve resource path for bundled executables."""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base = ROOT_DIR
    return os.path.join(base, *parts)


# === Пути и файлы ===
ROOT_DIR = get_root_dir()
SYSTEM_DIR = os.path.join(ROOT_DIR, 'system')
DOWNLOAD_LIST = os.path.join(SYSTEM_DIR, 'download-list.txt')
CONFIG_FILE = os.path.join(SYSTEM_DIR, 'config.ini')
LOG_FILE = os.path.join(SYSTEM_DIR, 'script.log')
INFO_FILE = os.path.join(SYSTEM_DIR, 'info.txt')
LOCK_FILE = os.path.join(SYSTEM_DIR, 'script.lock')
EPHEMERAL_MODE = getattr(sys, 'frozen', False)

DEFAULT_CONFIG = {
    'add_hotkey': 'ctrl+space',
    'download_hotkey': 'ctrl+shift+space',
}


def create_runtime_files() -> None:
    os.makedirs(SYSTEM_DIR, exist_ok=True)
    if not os.path.exists(DOWNLOAD_LIST):
        open(DOWNLOAD_LIST, 'a', encoding='utf-8').close()
    if not os.path.exists(LOG_FILE):
        open(LOG_FILE, 'a', encoding='utf-8').close()
    if not os.path.exists(INFO_FILE):
        open(INFO_FILE, 'a', encoding='utf-8').close()
    if not os.path.exists(CONFIG_FILE):
        parser = configparser.ConfigParser()
        parser['hotkeys'] = DEFAULT_CONFIG
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                parser.write(f)
        except Exception:
            pass


def cleanup_runtime_files() -> None:
    logging.shutdown()
    for path in (DOWNLOAD_LIST, CONFIG_FILE, LOG_FILE, INFO_FILE, LOCK_FILE):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except Exception:
            pass
    try:
        if os.path.isdir(SYSTEM_DIR) and not os.listdir(SYSTEM_DIR):
            os.rmdir(SYSTEM_DIR)
    except Exception:
        pass


# Prepare runtime files before configuring logging
create_runtime_files()
if EPHEMERAL_MODE:
    atexit.register(cleanup_runtime_files)


# Эти переменные инициализируются после загрузки конфигурации
DOWNLOADS_FOLDER = os.path.join(ROOT_DIR, 'Downloads')
VIDEOS_FOLDER = os.path.join(DOWNLOADS_FOLDER, 'Videos')
PLAYLIST_FOLDER = os.path.join(VIDEOS_FOLDER, 'Playlist Videos')
PICTURES_FOLDER = os.path.join(DOWNLOADS_FOLDER, 'Pictures')
WB_FOLDER = os.path.join(PICTURES_FOLDER, 'Wildberries')

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

# Флаг, указывающий выполняется ли сейчас скачивание
downloading = threading.Event()

# Изображения для разных состояний значка

def load_icon(name: str) -> Optional[Image.Image]:
    """Load an icon image, returning ``None`` on failure."""
    try:
        return Image.open(resource_path(name))
    except Exception:
        return None

ICON_DEFAULT = load_icon(os.path.join('icons', 'ico.ico'))
ICON_ACTIVE = load_icon(os.path.join('icons', 'act.ico'))
ICON_DOWNLOADING = load_icon(os.path.join('icons', 'dw.ico'))

def flash_tray_icon(icon: pystray.Icon, image: Image.Image, duration: float = 0.3) -> None:
    """Temporarily change the tray icon."""
    if not icon or not image:
        return
    current = icon.icon
    try:
        icon.icon = image
    except Exception:
        return

    def restore() -> None:
        try:
            icon.icon = current
        except Exception:
            pass

    threading.Timer(duration, restore).start()


def ensure_directories() -> None:
    """Создаёт директории для загрузок."""
    os.makedirs(VIDEOS_FOLDER, exist_ok=True)
    os.makedirs(PLAYLIST_FOLDER, exist_ok=True)
    os.makedirs(PICTURES_FOLDER, exist_ok=True)
    os.makedirs(WB_FOLDER, exist_ok=True)

def load_config() -> dict:
    parser = configparser.ConfigParser()
    if parser.read(CONFIG_FILE, encoding='utf-8'):
        try:
            data = dict(parser.items('hotkeys'))
            return {**DEFAULT_CONFIG, **data}
        except Exception as e:
            logging.error('Ошибка загрузки конфигурации: %s', e)
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict) -> None:
    parser = configparser.ConfigParser()
    parser['hotkeys'] = {
        'add_hotkey': cfg.get('add_hotkey', DEFAULT_CONFIG['add_hotkey']),
        'download_hotkey': cfg.get('download_hotkey', DEFAULT_CONFIG['download_hotkey'])
    }
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            parser.write(f)
    except Exception as e:
        logging.error('Ошибка сохранения конфигурации: %s', e)


def ensure_single_instance() -> None:
    """Предотвращает запуск нескольких экземпляров скрипта."""
    if sys.platform.startswith('win'):
        import msvcrt
        lock_file = open(LOCK_FILE, 'w')
        try:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            logging.info('Попытка запуска второго экземпляра.')
            print('Скрипт уже запущен.')
            sys.exit(0)

        def release_lock() -> None:
            try:
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                lock_file.close()
                os.remove(LOCK_FILE)
            except Exception:
                pass
            logging.info('Lock file released.')

        atexit.register(release_lock)


def download_video(url, folder):
    ydl_opts = {
        'format': 'best',
        'outtmpl': os.path.join(folder, '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'quiet': False,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        logging.error('Ошибка при скачивании YouTube-содержимого: %s', e)
        print(f"Ошибка при скачивании YouTube-содержимого: {e}")


def download_playlist(url, folder):
    ydl_opts = {
        'format': 'best',
        'outtmpl': os.path.join(folder, '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'quiet': False,
        'no_warnings': True,
        'yes_playlist': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        logging.error('Ошибка при скачивании плейлиста: %s', e)
        print(f"Ошибка при скачивании плейлиста: {e}")


def download_pinterest_image(url, folder):
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, 'html.parser')
        img_tag = soup.find('img')
        if img_tag and img_tag.get('src'):
            img_url = img_tag['src']
            print(f"Скачиваем изображение: {img_url}")
            img_data = requests.get(img_url).content
            filename = os.path.join(folder, os.path.basename(img_url.split("?")[0]))
            with open(filename, 'wb') as f:
                f.write(img_data)
            print(f"Изображение сохранено как: {filename}")
        else:
            print("Не удалось найти изображение на странице Pinterest.")
    except Exception as e:
        logging.error('Ошибка при скачивании изображения с Pinterest: %s', e)
        print(f"Ошибка при скачивании изображения с Pinterest: {e}")


def download_wb_images(url: str, folder: str) -> None:
    """Скачивает все изображения товара Wildberries."""
    try:
        m = re.search(r"/catalog/(\d+)/", url)
        if not m:
            print("Не удалось извлечь ID товара из ссылки WB.")
            return
        product_id = m.group(1)

        vol = int(product_id) // 100000
        part = int(product_id) // 1000

        headers = {"User-Agent": "Mozilla/5.0"}

        card_data = None
        host_used = None
        for host in range(100):
            card_url = (
                f"https://basket-{host:02d}.wbbasket.ru/vol{vol}/part{part}/"
                f"{product_id}/info/ru/card.json"
            )
            try:
                resp = requests.get(card_url, headers=headers, timeout=5)
                if resp.status_code == 200:
                    card_data = resp.json()
                    host_used = host
                    break
            except Exception:
                continue

        if not card_data:
            print("Не удалось получить данные о товаре WB.")
            return

        name = card_data.get("imt_name", f"wb_{product_id}")
        safe_name = "".join(c for c in name if c not in "\\/:*?\"<>|")
        product_folder = os.path.join(folder, safe_name)
        os.makedirs(product_folder, exist_ok=True)

        count = card_data.get("media", {}).get("photo_count") or 0
        if not count:
            print("Не удалось определить количество изображений WB.")
            return

        host_part = f"https://basket-{host_used:02d}.wbbasket.ru"

        for i in range(1, count + 1):
            img_url = (
                f"{host_part}/vol{vol}/part{part}/{product_id}/images/big/{i}.webp"
            )
            try:
                img_data = requests.get(img_url, headers=headers, timeout=10).content
                out_path = os.path.join(product_folder, f"{i}.webp")
                with open(out_path, "wb") as f:
                    f.write(img_data)
                print(f"Скачано: {out_path}")
            except Exception as e:
                logging.error("Не удалось скачать %s: %s", img_url, e)

        # Save textual information about the product
        lines: list[str] = []
        for group in card_data.get("grouped_options", []):
            group_name = group.get("group_name")
            if group_name:
                lines.append(group_name)
            for opt in group.get("options", []):
                name = opt.get("name", "").strip()
                value = opt.get("value", "").strip()
                if name or value:
                    lines.append(f"{name} - {value}")
            lines.append("")

        desc = card_data.get("description")
        if desc:
            lines.append("Описание")
            lines.append(desc.strip())

        if lines:
            info_path = os.path.join(product_folder, "info.txt")
            try:
                with open(info_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
            except Exception as e:
                logging.error("Не удалось сохранить описание WB: %s", e)
    except Exception as e:
        logging.error("Ошибка при скачивании изображений WB: %s", e)
        print(f"Ошибка при скачивании изображений WB: {e}")


def handle_url(url: str) -> None:
    """Определяет тип ссылки и запускает скачивание."""
    hostname = urlparse(url).hostname or ""
    hostname = hostname.lower()

    if "youtube.com/playlist" in url:
        logging.info('Скачиваем плейлист: %s', url)
        print(f"Это плейлист YouTube. Скачиваем всё в: {PLAYLIST_FOLDER}")
        download_playlist(url, PLAYLIST_FOLDER)

    elif "youtube.com" in hostname or "youtu.be" in hostname:
        logging.info('Скачиваем видео: %s', url)
        print(f"Это видео YouTube. Скачиваем в: {VIDEOS_FOLDER}")
        download_video(url, VIDEOS_FOLDER)

    elif "pinterest.com" in hostname:
        logging.info('Скачиваем изображение Pinterest: %s', url)
        print("Это Pinterest ссылка. Пытаемся скачать...")
        download_pinterest_image(url, PICTURES_FOLDER)

    elif "wildberries.ru" in hostname:
        logging.info('Скачиваем товар Wildberries: %s', url)
        print("Это ссылка Wildberries. Пытаемся скачать изображения...")
        download_wb_images(url, WB_FOLDER)

    else:
        logging.warning('Неизвестная ссылка: %s', url)
        print("Сайт не поддерживается этим скриптом.")


def download_all(icon: Optional[pystray.Icon] = None) -> None:
    """Скачивает все ссылки из файла download-list.txt в отдельном потоке."""
    if downloading.is_set():
        print("Скачивание уже выполняется.")
        return

    # —————— Смена иконки на dw.ico ——————
    if icon is not None and ICON_DOWNLOADING:
        try:
            icon.icon = ICON_DOWNLOADING
        except Exception:
            pass

    def worker() -> None:
        try:
            if not os.path.exists(DOWNLOAD_LIST):
                print("Файл download-list.txt не найден.")
                return

            with open(DOWNLOAD_LIST, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip()]

            if not urls:
                print("Список ссылок пуст.")
                return

            for url in urls:
                handle_url(url)

            open(DOWNLOAD_LIST, 'w', encoding='utf-8').close()
            print("Скачивание завершено!")
            if icon is not None:
                try:
                    icon.notify('Complete', 'Скачивание завершено')
                except Exception:
                    pass

        finally:
            downloading.clear()
            # —————— Возврат иконки ico.ico ——————
            if icon is not None and ICON_DEFAULT:
                try:
                    icon.icon = ICON_DEFAULT
                except Exception:
                    pass

    downloading.set()
    threading.Thread(target=worker, daemon=True).start()



def add_link_from_clipboard() -> None:
    """Copy the current selection and append it to ``download-list.txt``."""

    logging.info('Hotkey triggered: copying selection')

    captured = ''
    if clipboard_helper:
        captured = clipboard_helper.copy_selection()
    if not captured:
        captured = attempt_copy_selected_text()
    url = ""
    if captured:
        m = re.search(r"https?://\S+", captured)
        if m:
            url = m.group(0).strip()
    if not url:
        logging.info('Clipboard capture failed or empty')
        print("Не удалось скопировать ссылку. Возможно, она не выделена.")
        return

    if not URL_RE.search(url):
        logging.info('Clipboard text not a valid URL: %s', url)
        print("Скопированный текст не похож на ссылку.")
        return

    existing = []
    if os.path.exists(DOWNLOAD_LIST):
        with open(DOWNLOAD_LIST, 'r', encoding='utf-8') as f:
            existing = [line.strip() for line in f if line.strip()]

    if url in existing:
        logging.info('Дубликат ссылки: %s', url)
        print('Ссылка уже присутствует в списке.')
        return

    with open(DOWNLOAD_LIST, 'a', encoding='utf-8') as f:
        f.write(url + '\n')
    confirm = False
    try:
        with open(DOWNLOAD_LIST, 'r', encoding='utf-8') as f:
            confirm = url in [line.strip() for line in f if line.strip()]
    except Exception:
        pass
    if confirm:
        logging.info('Link added: %s', url)
        print(f"Добавлено в список: {url}")
    else:
        logging.error('Failed to confirm link save: %s', url)
        print("Не удалось добавить ссылку в список.")


def main() -> None:
    """Запускает горячие клавиши и значок в трее."""
    ensure_single_instance()
    global clipboard_helper
    clipboard_helper = ClipboardHelper()
    atexit.register(clipboard_helper.stop)

    config = load_config()
    ensure_directories()
    if not os.path.exists(DOWNLOAD_LIST):
        open(DOWNLOAD_LIST, 'a', encoding='utf-8').close()

    add_hotkey = config.get('add_hotkey', DEFAULT_CONFIG['add_hotkey'])
    download_hotkey = config.get('download_hotkey', DEFAULT_CONFIG['download_hotkey'])

    # Функция-обёртка для добавления ссылки с краткой сменой иконки
    def on_add(icon: pystray.Icon):
        flash_tray_icon(icon, ICON_ACTIVE)
        add_link_from_clipboard()

    # Меняем горячую клавишу
    def change_hotkey(icon, item):
        icon.notify('Настройка', 'Нажмите новое сочетание и Enter')
        hotkey_manager.unregister_all()
        hotkey_manager.stop_listener()
        try:
            new_key = keyboard.read_hotkey()
            if new_key:
                config['add_hotkey'] = new_key
                save_config(config)
                icon.notify('Готово', f'Новая клавиша: {new_key}')
        except Exception as e:
            logging.error('Ошибка смены горячей клавиши: %s', e)
        finally:
            hotkey_manager.start_listener()
            # Восстанавливаем привязки
            hotkey_manager.register(config['add_hotkey'], lambda: on_add(icon))
            hotkey_manager.register(config['download_hotkey'], lambda: download_all(icon))

    # Меню «Скачать»
    def on_download(icon, item):
        download_all(icon)

    # Выход
    def on_exit(icon, item):
        icon.stop()

    # Открыть список загрузок
    def open_list(icon, item):
        try:
            if sys.platform.startswith('win'):
                os.startfile(DOWNLOAD_LIST)
            else:
                subprocess.Popen(['xdg-open', DOWNLOAD_LIST])
        except Exception as e:
            logging.error('Не удалось открыть файл со списком: %s', e)

    # Открыть папку загрузок
    def open_folder(icon, item):
        try:
            if sys.platform.startswith('win'):
                os.startfile(DOWNLOADS_FOLDER)
            else:
                subprocess.Popen(['xdg-open', DOWNLOADS_FOLDER])
        except Exception as e:
            logging.error('Не удалось открыть папку загрузок: %s', e)

    # Информация
    def show_info(icon, item):
        try:
            if os.path.exists(INFO_FILE):
                if sys.platform.startswith('win'):
                    os.startfile(INFO_FILE)
                else:
                    subprocess.Popen(['xdg-open', INFO_FILE])
            else:
                icon.notify('Информация', 'Файл info.txt не найден')
        except Exception as e:
            logging.error('Не удалось открыть info.txt: %s', e)

    # Составляем меню
    menu = pystray.Menu(
        pystray.MenuItem('Скачать', on_download),
        pystray.MenuItem('Список загрузок', open_list),
        pystray.MenuItem('Открыть папку для загрузки', open_folder),
        pystray.MenuItem('Горячие клавиши', change_hotkey),
        pystray.MenuItem('Инфо', show_info),
        pystray.MenuItem('Выход', on_exit),
    )

    # Иконка в трее
    tray_icon = pystray.Icon('YTDownloader', ICON_DEFAULT, 'YT Downloader', menu)

    # Привязка горячих клавиш
    hotkey_manager.register(add_hotkey, lambda: on_add(tray_icon))
    hotkey_manager.register(download_hotkey, lambda: download_all(tray_icon))

    print(f"Значок размещён в трее. Горячие клавиши {add_hotkey} и {download_hotkey} активны.")
    tray_icon.run()
    hotkey_manager.unregister_all()
    if clipboard_helper:
        clipboard_helper.stop()
    print('Скрипт завершён.')

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
