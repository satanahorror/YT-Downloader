"""
YT Downloader v2.0 — десктопное приложение с поиском и скачиванием.
Использует yt-dlp. ffmpeg вшивается при сборке.

Зависимости:
    pip install customtkinter yt-dlp Pillow

Сборка в .exe:
    python build_exe.py
"""

import customtkinter as ctk
import threading
import subprocess
import sys
import os
import re
import json
import shutil
import io
import urllib.request
from tkinter import filedialog, messagebox
from PIL import Image

# ══════════════════════════════════════════════════════════════════════
#  Тема
# ══════════════════════════════════════════════════════════════════════

APP_NAME = "YT Downloader"
APP_VERSION = "2.0"

BG_DARK       = "#0c0c0c"
BG_CARD       = "#181818"
BG_INPUT      = "#111111"
BORDER        = "#282828"
ACCENT        = "#ff2d55"
ACCENT_HOVER  = "#ff4f73"
ACCENT_DIM    = "#3a1020"
ACCENT_BLUE   = "#3a86ff"
ACCENT_BLUE_H = "#5a9fff"
TEXT_PRIMARY   = "#f0f0f0"
TEXT_SECONDARY = "#888888"
TEXT_DIM       = "#505050"
SUCCESS        = "#34c759"
WARNING        = "#ffcc00"
ERROR          = "#ff3b30"

QUALITIES = ["Лучшее", "2160p (4K)", "1080p (Full HD)", "720p (HD)", "480p", "360p"]
QUALITY_MAP = {
    "Лучшее": None, "2160p (4K)": "2160", "1080p (Full HD)": "1080",
    "720p (HD)": "720", "480p": "480", "360p": "360",
}
AUDIO_FORMATS = ["mp3", "m4a", "opus", "flac", "wav"]


# ══════════════════════════════════════════════════════════════════════
#  Утилиты
# ══════════════════════════════════════════════════════════════════════

def get_default_download_dir():
    d = os.path.join(os.path.expanduser("~"), "Downloads", "YouTube")
    os.makedirs(d, exist_ok=True)
    return d


def resource_path(relative_path):
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)


def find_ffmpeg():
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "ffmpeg"),
        resource_path("ffmpeg"),
    ]
    for folder in candidates:
        for name in ("ffmpeg.exe", "ffmpeg"):
            if os.path.isfile(os.path.join(folder, name)):
                return folder
    if shutil.which("ffmpeg"):
        return None
    return ""


def format_duration(seconds):
    if not seconds:
        return "??:??"
    seconds = int(seconds)
    h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
    return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"


def format_views(n):
    if not n:
        return ""
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M просм."
    if n >= 1_000:
        return f"{n / 1_000:.0f}K просм."
    return f"{n} просм."


def load_thumbnail(url, size=(160, 90)):
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = resp.read()
        img = Image.open(io.BytesIO(data))
        img = img.resize(size, Image.LANCZOS)
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════
#  Карточка результата поиска
# ══════════════════════════════════════════════════════════════════════

class SearchResultCard(ctk.CTkFrame):
    def __init__(self, master, video_data, on_select, **kwargs):
        super().__init__(master, fg_color=BG_CARD, corner_radius=10,
                         border_width=1, border_color=BORDER, height=100, **kwargs)
        self.pack_propagate(False)
        self.video_data = video_data
        self.on_select = on_select

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="both", expand=True, padx=10, pady=8)

        # Превью
        self.thumb_label = ctk.CTkLabel(row, text="⏳", width=160, height=90,
                                         fg_color=BG_INPUT, corner_radius=6)
        self.thumb_label.pack(side="left", padx=(0, 12))

        # Инфо
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True)

        title = video_data.get("title", "Без названия")
        if len(title) > 70:
            title = title[:67] + "..."

        ctk.CTkLabel(info, text=title,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      text_color=TEXT_PRIMARY, anchor="w", wraplength=340
                      ).pack(anchor="w")

        channel = video_data.get("channel", video_data.get("uploader", ""))
        ctk.CTkLabel(info, text=channel,
                      font=ctk.CTkFont(size=11), text_color=TEXT_SECONDARY, anchor="w"
                      ).pack(anchor="w", pady=(2, 0))

        meta_parts = []
        dur = format_duration(video_data.get("duration"))
        if dur:
            meta_parts.append(dur)
        views = format_views(video_data.get("view_count"))
        if views:
            meta_parts.append(views)

        ctk.CTkLabel(info, text="  •  ".join(meta_parts),
                      font=ctk.CTkFont(size=11), text_color=TEXT_DIM, anchor="w"
                      ).pack(anchor="w", pady=(2, 0))

        # Кнопка
        ctk.CTkButton(
            row, text="⬇", width=42, height=42,
            font=ctk.CTkFont(size=18),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            corner_radius=8, command=self._select
        ).pack(side="right", padx=(10, 0))

        # Ховер
        self.bind("<Enter>", lambda e: self.configure(border_color=ACCENT_DIM))
        self.bind("<Leave>", lambda e: self.configure(border_color=BORDER))

        # Превью в фоне
        thumb_url = video_data.get("thumbnail")
        if thumb_url:
            threading.Thread(target=self._load_thumb, args=(thumb_url,), daemon=True).start()

    def _load_thumb(self, url):
        img = load_thumbnail(url)
        if img:
            self.after(0, lambda: self.thumb_label.configure(image=img, text=""))

    def _select(self):
        url = self.video_data.get("webpage_url") or self.video_data.get("url", "")
        self.on_select(url, self.video_data.get("title", ""))


# ══════════════════════════════════════════════════════════════════════
#  Главное приложение
# ══════════════════════════════════════════════════════════════════════

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("780x780")
        self.minsize(680, 650)
        self.configure(fg_color=BG_DARK)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.download_dir = get_default_download_dir()
        self.is_downloading = False
        self.is_searching = False
        self.process = None
        self.ffmpeg_dir = find_ffmpeg()

        self._build_ui()

    def _build_ui(self):
        # Шапка
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(18, 0))

        ctk.CTkLabel(header, text="▶  YT Downloader",
                      font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
                      text_color=TEXT_PRIMARY).pack(side="left")

        ctk.CTkLabel(header, text=f"v{APP_VERSION}",
                      font=ctk.CTkFont(size=11), text_color=TEXT_DIM
                      ).pack(side="left", padx=(8, 0), pady=(6, 0))

        if self.ffmpeg_dir == "":
            ff_text, ff_color = "ffmpeg: ⚠ нет", WARNING
        elif self.ffmpeg_dir is None:
            ff_text, ff_color = "ffmpeg: ✔", SUCCESS
        else:
            ff_text, ff_color = "ffmpeg: ✔ встроенный", SUCCESS

        ctk.CTkLabel(header, text=ff_text,
                      font=ctk.CTkFont(size=11), text_color=ff_color
                      ).pack(side="right")

        # Вкладки
        self.tabview = ctk.CTkTabview(
            self, fg_color=BG_DARK,
            segmented_button_fg_color=BG_CARD,
            segmented_button_selected_color=ACCENT,
            segmented_button_selected_hover_color=ACCENT_HOVER,
            segmented_button_unselected_color=BG_INPUT,
            segmented_button_unselected_hover_color="#252525",
            corner_radius=12,
        )
        self.tabview.pack(fill="both", expand=True, padx=24, pady=(10, 20))

        self.tab_search = self.tabview.add("🔍 Поиск")
        self.tab_download = self.tabview.add("⬇ Скачивание")

        self._build_search_tab()
        self._build_download_tab()

    # ── ПОИСК ──────────────────────────────────────────────────────

    def _build_search_tab(self):
        tab = self.tab_search

        sf = ctk.CTkFrame(tab, fg_color=BG_CARD, corner_radius=10,
                           border_width=1, border_color=BORDER)
        sf.pack(fill="x", pady=(0, 10))

        sr = ctk.CTkFrame(sf, fg_color="transparent")
        sr.pack(fill="x", padx=14, pady=12)

        self.search_entry = ctk.CTkEntry(
            sr, placeholder_text="Поиск на YouTube...",
            font=ctk.CTkFont(size=14), height=42,
            fg_color=BG_INPUT, border_color=BORDER,
            border_width=1, corner_radius=8, text_color=TEXT_PRIMARY,
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.search_entry.bind("<Return>", lambda e: self._do_search())

        self.search_btn = ctk.CTkButton(
            sr, text="🔍 Найти", width=110, height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=ACCENT_BLUE, hover_color=ACCENT_BLUE_H,
            corner_radius=8, command=self._do_search
        )
        self.search_btn.pack(side="right")

        self.search_status = ctk.CTkLabel(tab, text="",
                                           font=ctk.CTkFont(size=11), text_color=TEXT_DIM)
        self.search_status.pack(anchor="w")

        self.results_scroll = ctk.CTkScrollableFrame(
            tab, fg_color="transparent",
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=TEXT_DIM,
        )
        self.results_scroll.pack(fill="both", expand=True, pady=(6, 0))

    def _do_search(self):
        query = self.search_entry.get().strip()
        if not query or self.is_searching:
            return

        self.is_searching = True
        self.search_btn.configure(text="⏳ Ищу...", state="disabled")
        self.search_status.configure(text=f"Поиск: «{query}»...", text_color=ACCENT_BLUE)

        for w in self.results_scroll.winfo_children():
            w.destroy()

        threading.Thread(target=self._search_thread, args=(query,), daemon=True).start()

    def _search_thread(self, query):
        cmd = [
            sys.executable, "-m", "yt_dlp",
            f"ytsearch10:{query}",
            "--dump-json", "--flat-playlist",
            "--no-download", "--no-warnings",
            "--encoding", "utf-8",
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )

            results = []
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if line:
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

            self.after(0, lambda: self._show_results(results, query))

        except subprocess.TimeoutExpired:
            self.after(0, lambda: self.search_status.configure(
                text="⚠ Таймаут. Попробуйте снова.", text_color=WARNING))
        except FileNotFoundError:
            self.after(0, lambda: self.search_status.configure(
                text="✘ yt-dlp не найден! pip install yt-dlp", text_color=ERROR))
        except Exception as e:
            self.after(0, lambda: self.search_status.configure(
                text=f"✘ Ошибка: {e}", text_color=ERROR))
        finally:
            self.after(0, lambda: self.search_btn.configure(text="🔍 Найти", state="normal"))
            self.is_searching = False

    def _show_results(self, results, query):
        for w in self.results_scroll.winfo_children():
            w.destroy()

        if not results:
            self.search_status.configure(text=f"Ничего не найдено: «{query}»", text_color=WARNING)
            return

        self.search_status.configure(
            text=f"Найдено: {len(results)} видео", text_color=SUCCESS)

        for video in results:
            card = SearchResultCard(self.results_scroll, video, self._on_video_select)
            card.pack(fill="x", pady=(0, 6))

    def _on_video_select(self, url, title):
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, url)
        self.tabview.set("⬇ Скачивание")

    # ── СКАЧИВАНИЕ ─────────────────────────────────────────────────

    def _build_download_tab(self):
        tab = self.tab_download

        # URL
        uf = ctk.CTkFrame(tab, fg_color=BG_CARD, corner_radius=10,
                           border_width=1, border_color=BORDER)
        uf.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(uf, text="ССЫЛКА",
                      font=ctk.CTkFont(size=10, weight="bold"),
                      text_color=TEXT_SECONDARY).pack(anchor="w", padx=14, pady=(10, 4))

        ir = ctk.CTkFrame(uf, fg_color="transparent")
        ir.pack(fill="x", padx=14, pady=(0, 12))

        self.url_entry = ctk.CTkEntry(
            ir, placeholder_text="https://youtube.com/watch?v=... или найдите через 🔍 Поиск",
            font=ctk.CTkFont(size=13), height=40,
            fg_color=BG_INPUT, border_color=BORDER,
            border_width=1, corner_radius=8, text_color=TEXT_PRIMARY,
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(ir, text="📋", width=40, height=40,
                       font=ctk.CTkFont(size=16),
                       fg_color=BORDER, hover_color="#3a3a3a",
                       corner_radius=8, command=self._paste_url).pack(side="right")

        # Настройки
        sf = ctk.CTkFrame(tab, fg_color=BG_CARD, corner_radius=10,
                           border_width=1, border_color=BORDER)
        sf.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(sf, text="НАСТРОЙКИ",
                      font=ctk.CTkFont(size=10, weight="bold"),
                      text_color=TEXT_SECONDARY).pack(anchor="w", padx=14, pady=(10, 6))

        # Режим
        mr = ctk.CTkFrame(sf, fg_color="transparent")
        mr.pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkLabel(mr, text="Режим", font=ctk.CTkFont(size=12),
                      text_color=TEXT_PRIMARY, width=90).pack(side="left")

        self.mode_var = ctk.StringVar(value="video")
        self.mode_seg = ctk.CTkSegmentedButton(
            mr, values=["video", "audio"], variable=self.mode_var,
            font=ctk.CTkFont(size=12),
            selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
            unselected_color=BG_INPUT, unselected_hover_color="#252525",
            corner_radius=8, command=self._on_mode_change
        )
        self.mode_seg.pack(side="left", padx=(8, 0))

        # Качество
        self.quality_row = ctk.CTkFrame(sf, fg_color="transparent")
        self.quality_row.pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkLabel(self.quality_row, text="Качество", font=ctk.CTkFont(size=12),
                      text_color=TEXT_PRIMARY, width=90).pack(side="left")

        self.quality_var = ctk.StringVar(value="Лучшее")
        ctk.CTkOptionMenu(
            self.quality_row, values=QUALITIES, variable=self.quality_var,
            font=ctk.CTkFont(size=12),
            fg_color=BG_INPUT, button_color=BORDER, button_hover_color="#3a3a3a",
            dropdown_fg_color=BG_CARD, dropdown_hover_color=ACCENT_DIM,
            corner_radius=8, width=190,
        ).pack(side="left", padx=(8, 0))

        # Аудио формат (скрыт)
        self.audio_row = ctk.CTkFrame(sf, fg_color="transparent")

        ctk.CTkLabel(self.audio_row, text="Формат", font=ctk.CTkFont(size=12),
                      text_color=TEXT_PRIMARY, width=90).pack(side="left")

        self.audio_var = ctk.StringVar(value="mp3")
        ctk.CTkOptionMenu(
            self.audio_row, values=AUDIO_FORMATS, variable=self.audio_var,
            font=ctk.CTkFont(size=12),
            fg_color=BG_INPUT, button_color=BORDER, button_hover_color="#3a3a3a",
            dropdown_fg_color=BG_CARD, dropdown_hover_color=ACCENT_DIM,
            corner_radius=8, width=190,
        ).pack(side="left", padx=(8, 0))

        # Чекбоксы
        cr = ctk.CTkFrame(sf, fg_color="transparent")
        cr.pack(fill="x", padx=14, pady=(0, 12))

        self.subs_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(cr, text="Субтитры", variable=self.subs_var,
                          font=ctk.CTkFont(size=12),
                          fg_color=ACCENT, hover_color=ACCENT_HOVER,
                          border_color=BORDER).pack(side="left", padx=(0, 20))

        self.playlist_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(cr, text="Весь плейлист", variable=self.playlist_var,
                          font=ctk.CTkFont(size=12),
                          fg_color=ACCENT, hover_color=ACCENT_HOVER,
                          border_color=BORDER).pack(side="left")

        # Папка
        df = ctk.CTkFrame(tab, fg_color=BG_CARD, corner_radius=10,
                           border_width=1, border_color=BORDER)
        df.pack(fill="x", pady=(0, 10))

        di = ctk.CTkFrame(df, fg_color="transparent")
        di.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(di, text="📂", font=ctk.CTkFont(size=16)).pack(side="left")

        self.dir_label = ctk.CTkLabel(di, text=self.download_dir,
                                       font=ctk.CTkFont(size=11),
                                       text_color=TEXT_SECONDARY, anchor="w")
        self.dir_label.pack(side="left", fill="x", expand=True, padx=(8, 8))

        ctk.CTkButton(di, text="Изменить", width=80, height=30,
                       font=ctk.CTkFont(size=11),
                       fg_color=BORDER, hover_color="#3a3a3a",
                       corner_radius=6, command=self._choose_dir).pack(side="right")

        # Кнопка
        self.download_btn = ctk.CTkButton(
            tab, text="⬇  СКАЧАТЬ", height=48,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            corner_radius=10, command=self._start_download
        )
        self.download_btn.pack(fill="x", pady=(0, 8))

        # Прогресс
        self.progress_bar = ctk.CTkProgressBar(tab, height=5,
                                                fg_color=BORDER, progress_color=ACCENT, corner_radius=3)
        self.progress_bar.pack(fill="x", pady=(0, 6))
        self.progress_bar.set(0)

        # Лог
        self.log_box = ctk.CTkTextbox(
            tab, height=90, font=ctk.CTkFont(family="Consolas", size=10),
            fg_color=BG_INPUT, border_color=BORDER, border_width=1,
            corner_radius=8, text_color=TEXT_SECONDARY, state="disabled"
        )
        self.log_box.pack(fill="both", expand=True)

        self.status_label = ctk.CTkLabel(tab, text="Готово к работе",
                                          font=ctk.CTkFont(size=10),
                                          text_color=TEXT_DIM, anchor="w")
        self.status_label.pack(fill="x", pady=(4, 0))

    # ── Логика ─────────────────────────────────────────────────────

    def _paste_url(self):
        try:
            t = self.clipboard_get()
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, t.strip())
        except Exception:
            pass

    def _choose_dir(self):
        d = filedialog.askdirectory(initialdir=self.download_dir)
        if d:
            self.download_dir = d
            self.dir_label.configure(text=d)

    def _on_mode_change(self, value):
        if value == "audio":
            self.quality_row.pack_forget()
            self.audio_row.pack(in_=self.quality_row.master, fill="x", padx=14,
                                pady=(0, 8), after=self.mode_seg.master)
        else:
            self.audio_row.pack_forget()
            self.quality_row.pack(in_=self.quality_row.master, fill="x", padx=14,
                                  pady=(0, 8), after=self.mode_seg.master)

    def _log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _set_status(self, text, color=TEXT_DIM):
        self.status_label.configure(text=text, text_color=color)

    def _set_downloading(self, state):
        self.is_downloading = state
        if state:
            self.download_btn.configure(text="⏹  ОТМЕНИТЬ", fg_color=ERROR, hover_color="#cc2020")
        else:
            self.download_btn.configure(text="⬇  СКАЧАТЬ", fg_color=ACCENT, hover_color=ACCENT_HOVER)

    def _start_download(self):
        if self.is_downloading:
            self._cancel_download()
            return

        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Нет ссылки", "Вставьте ссылку или найдите видео через поиск.")
            return

        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self.progress_bar.set(0)
        self._set_downloading(True)
        self._set_status("Скачивание...", ACCENT)

        threading.Thread(target=self._download_thread, args=(url,), daemon=True).start()

    def _cancel_download(self):
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass
        self._set_downloading(False)
        self._set_status("Отменено", WARNING)
        self._log("⚠ Отменено.")

    def _build_cmd(self, url):
        template = os.path.join(self.download_dir, "%(title)s [%(id)s].%(ext)s")
        cmd = [sys.executable, "-m", "yt_dlp"]

        if self.mode_var.get() == "audio":
            cmd += ["-x", "--audio-format", self.audio_var.get(), "--audio-quality", "0"]
        else:
            q = QUALITY_MAP.get(self.quality_var.get())
            if q:
                cmd += ["-f", f"bestvideo[height<={q}]+bestaudio/best[height<={q}]",
                        "--merge-output-format", "mp4"]
            else:
                cmd += ["-f", "bestvideo+bestaudio/best", "--merge-output-format", "mp4"]

        if self.subs_var.get():
            cmd += ["--write-subs", "--sub-langs", "all", "--embed-subs"]
        if not self.playlist_var.get():
            cmd += ["--no-playlist"]
        if self.ffmpeg_dir and os.path.isdir(self.ffmpeg_dir):
            cmd += ["--ffmpeg-location", self.ffmpeg_dir]

        cmd += ["-o", template, "--newline", "--no-mtime", "--encoding", "utf-8", url]
        return cmd

    def _download_thread(self, url):
        cmd = self._build_cmd(url)
        self._log("▶ Запуск...")

        try:
            self.process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )

            for line in self.process.stdout:
                line = line.strip()
                if not line:
                    continue
                match = re.search(r"(\d+\.?\d*)%", line)
                if match:
                    pct = float(match.group(1)) / 100.0
                    self.progress_bar.set(pct)
                    self.after(0, lambda l=line: self._set_status(l, ACCENT))
                self.after(0, lambda l=line: self._log(l))

            self.process.wait()

            if self.process.returncode == 0:
                self.after(0, lambda: self.progress_bar.set(1.0))
                self.after(0, lambda: self._set_status("✔ Готово!", SUCCESS))
                self.after(0, lambda: self._log(f"\n✔ Файлы: {self.download_dir}"))
            else:
                self.after(0, lambda: self._set_status(
                    f"✘ Ошибка (код {self.process.returncode})", ERROR))

        except FileNotFoundError:
            self.after(0, lambda: self._set_status("✘ yt-dlp не найден!", ERROR))
            self.after(0, lambda: self._log("✘ pip install yt-dlp"))
        except Exception as e:
            self.after(0, lambda: self._set_status(f"✘ {e}", ERROR))
            self.after(0, lambda: self._log(f"✘ {e}"))
        finally:
            self.process = None
            self.after(0, lambda: self._set_downloading(False))


if __name__ == "__main__":
    app = App()
    app.mainloop()
