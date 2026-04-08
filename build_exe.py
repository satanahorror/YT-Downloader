"""
Скрипт сборки YouTube Downloader в .exe
Автоматически скачивает ffmpeg и вшивает его в exe.

Использование:
    python build_exe.py

Требования:
    pip install pyinstaller customtkinter yt-dlp
"""

import subprocess
import sys
import os
import platform
import zipfile
import urllib.request

FFMPEG_WIN_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
FFMPEG_DIR = "ffmpeg"


def install_deps():
    """Устанавливает недостающие зависимости."""
    deps = {"pyinstaller": "pyinstaller", "customtkinter": "customtkinter", "yt_dlp": "yt-dlp"}
    missing = []
    for module, pip_name in deps.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(pip_name)

    if missing:
        print(f"\n⚠  Устанавливаю: {', '.join(missing)}")
        subprocess.run([sys.executable, "-m", "pip", "install"] + missing, check=True)
        print()


def download_ffmpeg():
    """Скачивает ffmpeg для Windows и распаковывает в папку ./ffmpeg."""
    if os.path.isdir(FFMPEG_DIR) and any(
        f.startswith("ffmpeg") for f in os.listdir(FFMPEG_DIR)
    ):
        print(f"✔  ffmpeg уже есть в ./{FFMPEG_DIR}/")
        return True

    if platform.system() != "Windows":
        print("⚠  Автоскачивание ffmpeg — только для Windows.")
        print("   На Linux/macOS установите ffmpeg через пакетный менеджер")
        print(f"   и положите ffmpeg, ffprobe в папку ./{FFMPEG_DIR}/")
        return os.path.isdir(FFMPEG_DIR)

    zip_path = "ffmpeg_download.zip"
    print(f"⬇  Скачиваю ffmpeg...")
    print(f"   {FFMPEG_WIN_URL}\n")

    try:
        urllib.request.urlretrieve(FFMPEG_WIN_URL, zip_path, _download_progress)
        print("\n\n📦  Распаковываю...")

        with zipfile.ZipFile(zip_path, "r") as zf:
            bin_files = [f for f in zf.namelist() if "/bin/" in f and not f.endswith("/")]
            os.makedirs(FFMPEG_DIR, exist_ok=True)
            for f in bin_files:
                filename = os.path.basename(f)
                if filename:
                    with zf.open(f) as src, open(os.path.join(FFMPEG_DIR, filename), "wb") as dst:
                        dst.write(src.read())
                    print(f"   ✔ {filename}")

        os.remove(zip_path)
        print(f"\n✔  ffmpeg готов в ./{FFMPEG_DIR}/\n")
        return True

    except Exception as e:
        print(f"\n✘  Ошибка скачивания ffmpeg: {e}")
        print("   Скачайте вручную с https://ffmpeg.org/download.html")
        print(f"   и положите ffmpeg.exe, ffprobe.exe в папку ./{FFMPEG_DIR}/")
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return False


def _download_progress(block_num, block_size, total_size):
    downloaded = block_num * block_size
    if total_size > 0:
        pct = min(downloaded / total_size * 100, 100)
        bar = "█" * int(pct // 2) + "░" * (50 - int(pct // 2))
        print(f"\r   [{bar}] {pct:.0f}%  ({downloaded // 1024 // 1024}MB)", end="", flush=True)


def build():
    """Собирает .exe через PyInstaller."""
    import customtkinter
    ctk_path = os.path.dirname(customtkinter.__file__)

    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "youtube_downloader_gui.py")

    if not os.path.isfile(script):
        print(f"✘  Не найден {script}")
        print("   Положите build_exe.py и youtube_downloader_gui.py в одну папку.")
        sys.exit(1)

    sep = ";" if platform.system() == "Windows" else ":"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",                                  # папка (быстрее запуск)
        "--windowed",                                # без консоли
        "--name", "YT_Downloader",
        f"--add-data={ctk_path}{sep}customtkinter",  # CustomTkinter
        "--clean",
    ]

    # Вшиваем ffmpeg если папка есть
    if os.path.isdir(FFMPEG_DIR) and os.listdir(FFMPEG_DIR):
        cmd.append(f"--add-data={os.path.abspath(FFMPEG_DIR)}{sep}ffmpeg")
        print(f"📦  ffmpeg будет вшит из ./{FFMPEG_DIR}/")
    else:
        print("⚠  ffmpeg не найден — собираю без него")

    cmd.append(script)

    print(f"\n🔧  Запуск PyInstaller...\n")

    result = subprocess.run(cmd)

    if result.returncode == 0:
        dist_dir = os.path.join("dist", "YT_Downloader")
        print(f"\n{'═' * 58}")
        print(f"  ✔  Сборка завершена!")
        print(f"  📁 {os.path.abspath(dist_dir)}")

        total = sum(
            os.path.getsize(os.path.join(dp, f))
            for dp, _, fns in os.walk(dist_dir) for f in fns
        ) if os.path.isdir(dist_dir) else 0
        print(f"  📦 Размер: {total / 1024 / 1024:.0f} MB")
        print(f"{'═' * 58}\n")
        print(f"  Запускайте: {os.path.join(dist_dir, 'YT_Downloader.exe')}\n")

        if platform.system() == "Windows":
            os.startfile(os.path.abspath(dist_dir))
    else:
        print(f"\n✘  Ошибка сборки (код {result.returncode})")


def main():
    print("═" * 58)
    print("  🔨  Сборка YT Downloader → .exe (с ffmpeg)")
    print("═" * 58, "\n")

    install_deps()
    download_ffmpeg()
    build()


if __name__ == "__main__":
    main()
