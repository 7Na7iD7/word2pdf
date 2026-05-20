import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
import subprocess
import platform
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.converter import Converter, ConversionResult, ConversionStats, detect_backend


COLORS = {
    "bg":           "#0f1117",
    "bg_card":      "#171b26",
    "bg_panel":     "#1c2130",
    "bg_item":      "#212638",
    "bg_item_alt":  "#1a1f2e",
    "accent":       "#4f8ef7",
    "accent_dim":   "#2d5ac7",
    "success":      "#3ecf8e",
    "warning":      "#f5a623",
    "danger":       "#ef4444",
    "danger_dim":   "#991b1b",
    "text":         "#e8eaf0",
    "text_dim":     "#8892a4",
    "text_muted":   "#4a5568",
    "border":       "#2a3148",
    "border_light": "#3a4460",
    "highlight":    "#263354",
    "scrollbar":    "#2a3148",
}

FONTS = {
    "title":    ("Segoe UI", 18, "bold"),
    "heading":  ("Segoe UI", 11, "bold"),
    "body":     ("Segoe UI", 10),
    "small":    ("Segoe UI", 9),
    "mono":     ("Consolas", 9),
    "persian":  ("Tahoma", 10),
}


class StatusBar(tk.Frame):
    """Bottom status bar with live info."""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=COLORS["bg_panel"], height=28, **kw)
        self.pack_propagate(False)

        self._backend_var = tk.StringVar(value="detecting…")
        self._msg_var = tk.StringVar(value="آماده")

        tk.Label(self, textvariable=self._msg_var,
                 bg=COLORS["bg_panel"], fg=COLORS["text_dim"],
                 font=FONTS["small"], anchor="w").pack(side="left", padx=12)

        tk.Label(self, textvariable=self._backend_var,
                 bg=COLORS["bg_panel"], fg=COLORS["accent"],
                 font=FONTS["small"], anchor="e").pack(side="right", padx=12)

    def set_message(self, msg: str, color: str = None):
        self._msg_var.set(msg)

    def set_backend(self, backend: str):
        labels = {
            "libreoffice": "⚙ LibreOffice",
            "win32com":    "⚙ Microsoft Word",
            "docx2pdf":    "⚙ docx2pdf",
            "unavailable": "⚠ موتور یافت نشد",
        }
        self._backend_var.set(labels.get(backend, backend))


class FileListPanel(tk.Frame):
    """Drag-and-drop-ready file list with row management."""

    def __init__(self, parent, on_change=None, **kw):
        super().__init__(parent, bg=COLORS["bg_card"], **kw)
        self._on_change = on_change
        self._files: list[str] = []
        self._selected: set[int] = set()
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=COLORS["bg_panel"])
        hdr.pack(fill="x")

        tk.Label(hdr, text="📄  فایل‌های انتخاب‌شده",
                 bg=COLORS["bg_panel"], fg=COLORS["text"],
                 font=FONTS["heading"], anchor="e").pack(side="right", padx=14, pady=8)

        self._count_label = tk.Label(hdr, text="۰ فایل",
                                     bg=COLORS["bg_panel"], fg=COLORS["text_dim"],
                                     font=FONTS["small"])
        self._count_label.pack(side="left", padx=14)

        # Listbox + scrollbar
        frame = tk.Frame(self, bg=COLORS["bg_card"])
        frame.pack(fill="both", expand=True, padx=1, pady=1)

        self._listbox = tk.Listbox(
            frame,
            selectmode="extended",
            bg=COLORS["bg_item"],
            fg=COLORS["text"],
            selectbackground=COLORS["highlight"],
            selectforeground=COLORS["accent"],
            activestyle="none",
            font=FONTS["body"],
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
        )
        scrollbar = tk.Scrollbar(frame, orient="vertical",
                                  command=self._listbox.yview,
                                  bg=COLORS["scrollbar"],
                                  troughcolor=COLORS["bg_item"],
                                  relief="flat", width=8)
        self._listbox.configure(yscrollcommand=scrollbar.set)
        self._listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._hint = tk.Label(
            frame,
            text="فایل‌های Word را اینجا بکشید\nیا از دکمه «افزودن» استفاده کنید",
            bg=COLORS["bg_item"], fg=COLORS["text_muted"],
            font=FONTS["persian"], justify="center"
        )
        self._hint.place(relx=0.5, rely=0.5, anchor="center")

    def add_files(self, paths: list[str]):
        existing = set(self._files)
        added = 0
        for p in paths:
            if p not in existing and p.lower().endswith((".doc", ".docx")):
                self._files.append(p)
                name = Path(p).name
                size_kb = os.path.getsize(p) / 1024
                self._listbox.insert("end", f"  {name}   ({size_kb:.0f} KB)")
                added += 1
        self._refresh_ui()
        return added

    def remove_selected(self):
        sel = list(self._listbox.curselection())
        for i in reversed(sel):
            self._listbox.delete(i)
            self._files.pop(i)
        self._refresh_ui()

    def clear_all(self):
        self._files.clear()
        self._listbox.delete(0, "end")
        self._refresh_ui()

    def get_files(self) -> list[str]:
        return list(self._files)

    def mark_done(self, index: int, success: bool):
        prefix = "  ✅ " if success else "  ❌ "
        current = self._listbox.get(index)
        # Strip old icon
        cleaned = current.lstrip().lstrip("✅❌⏳ ")
        self._listbox.delete(index)
        self._listbox.insert(index, f"  {prefix}{cleaned}")
        color = COLORS["success"] if success else COLORS["danger"]
        self._listbox.itemconfig(index, fg=color)

    def mark_converting(self, index: int):
        current = self._listbox.get(index)
        cleaned = current.lstrip().lstrip("✅❌⏳ ")
        self._listbox.delete(index)
        self._listbox.insert(index, f"  ⏳ {cleaned}")
        self._listbox.itemconfig(index, fg=COLORS["warning"])
        self._listbox.see(index)

    def _refresh_ui(self):
        count = len(self._files)
        self._count_label.config(text=f"{count} فایل")
        if count > 0:
            self._hint.place_forget()
        else:
            self._hint.place(relx=0.5, rely=0.5, anchor="center")
        if self._on_change:
            self._on_change(count)

    def __len__(self):
        return len(self._files)


class RoundedButton(tk.Canvas):
    """Custom canvas-based rounded button."""

    def __init__(self, parent, text, command=None,
                 bg=None, fg=None, hover_bg=None,
                 width=120, height=36, radius=8,
                 font=None, **kw):
        super().__init__(parent, width=width, height=height,
                         bg=parent["bg"], highlightthickness=0, **kw)
        self._bg = bg or COLORS["accent"]
        self._hover_bg = hover_bg or COLORS["accent_dim"]
        self._fg = fg or COLORS["text"]
        self._text = text
        self._command = command
        self._radius = radius
        self._font = font or FONTS["body"]
        self.btn_width = width
        self.btn_height = height

        self._draw(self._bg)
        self.bind("<Enter>", lambda e: self._draw(self._hover_bg))
        self.bind("<Leave>", lambda e: self._draw(self._bg))
        self.bind("<Button-1>", lambda e: self._click())

    def _draw(self, color):
        self.delete("all")
        r = self._radius
        w, h = self.btn_width, self.btn_height
        # Rounded rectangle
        self.create_arc(0, 0, 2*r, 2*r, start=90, extent=90, fill=color, outline=color)
        self.create_arc(w-2*r, 0, w, 2*r, start=0, extent=90, fill=color, outline=color)
        self.create_arc(0, h-2*r, 2*r, h, start=180, extent=90, fill=color, outline=color)
        self.create_arc(w-2*r, h-2*r, w, h, start=270, extent=90, fill=color, outline=color)
        self.create_rectangle(r, 0, w-r, h, fill=color, outline=color)
        self.create_rectangle(0, r, w, h-r, fill=color, outline=color)
        self.create_text(w//2, h//2, text=self._text,
                         fill=self._fg, font=self._font)

    def _click(self):
        self._draw(self._hover_bg)
        self.after(100, lambda: self._draw(self._bg))
        if self._command:
            self._command()

    def configure_state(self, enabled: bool):
        self._bg = (COLORS["accent"] if enabled else COLORS["bg_item"])
        self._hover_bg = (COLORS["accent_dim"] if enabled else COLORS["bg_item"])
        self._draw(self._bg)
        if not enabled:
            self.unbind("<Button-1>")
        else:
            self.bind("<Button-1>", lambda e: self._click())


class ProgressPanel(tk.Frame):
    """Progress bar + stats panel."""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=COLORS["bg_card"], **kw)
        self._build()

    def _build(self):
        bar_frame = tk.Frame(self, bg=COLORS["bg_card"])
        bar_frame.pack(fill="x", padx=16, pady=(12, 4))

        self._progress_label = tk.Label(bar_frame, text="در انتظار…",
                                         bg=COLORS["bg_card"], fg=COLORS["text_dim"],
                                         font=FONTS["small"], anchor="e")
        self._progress_label.pack(anchor="e")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Custom.Horizontal.TProgressbar",
                         troughcolor=COLORS["bg_item"],
                         background=COLORS["accent"],
                         bordercolor=COLORS["bg_item"],
                         lightcolor=COLORS["accent"],
                         darkcolor=COLORS["accent_dim"],
                         thickness=10)

        self._bar = ttk.Progressbar(bar_frame, style="Custom.Horizontal.TProgressbar",
                                     orient="horizontal", length=100, mode="determinate")
        self._bar.pack(fill="x", pady=(4, 0))

        stats_frame = tk.Frame(self, bg=COLORS["bg_card"])
        stats_frame.pack(fill="x", padx=16, pady=(8, 12))

        self._stats_labels = {}
        items = [
            ("success", "✅ موفق", COLORS["success"]),
            ("failed",  "❌ خطا",  COLORS["danger"]),
            ("speed",   "⚡ سرعت", COLORS["warning"]),
            ("time",    "⏱ زمان",  COLORS["text_dim"]),
        ]
        for key, label, color in items:
            cell = tk.Frame(stats_frame, bg=COLORS["bg_item"], padx=12, pady=6)
            cell.pack(side="left", padx=4, fill="x", expand=True)
            tk.Label(cell, text=label, bg=COLORS["bg_item"],
                     fg=COLORS["text_muted"], font=FONTS["small"]).pack()
            val = tk.Label(cell, text="—", bg=COLORS["bg_item"],
                           fg=color, font=FONTS["heading"])
            val.pack()
            self._stats_labels[key] = val

    def update(self, current: int, total: int, success: int, failed: int,
               elapsed: float):
        pct = int((current / total) * 100) if total > 0 else 0
        self._bar["value"] = pct
        self._progress_label.config(text=f"{current} / {total}   ({pct}%)")
        self._stats_labels["success"].config(text=str(success))
        self._stats_labels["failed"].config(text=str(failed))
        speed = (current / elapsed) if elapsed > 0 else 0
        self._stats_labels["speed"].config(text=f"{speed:.1f}/s")
        self._stats_labels["time"].config(text=f"{elapsed:.0f}s")

    def reset(self):
        self._bar["value"] = 0
        self._progress_label.config(text="در انتظار…")
        for lbl in self._stats_labels.values():
            lbl.config(text="—")


class LogPanel(tk.Frame):
    """Scrollable conversion log."""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=COLORS["bg_card"], **kw)
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=COLORS["bg_panel"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="📋  گزارش تبدیل",
                 bg=COLORS["bg_panel"], fg=COLORS["text"],
                 font=FONTS["heading"], anchor="e").pack(side="right", padx=14, pady=6)

        frame = tk.Frame(self, bg=COLORS["bg_card"])
        frame.pack(fill="both", expand=True, padx=1, pady=1)

        self._text = tk.Text(frame,
                              bg=COLORS["bg_item"], fg=COLORS["text_dim"],
                              font=FONTS["mono"],
                              borderwidth=0, highlightthickness=0,
                              state="disabled", wrap="none",
                              insertbackground=COLORS["text"])
        sb_y = tk.Scrollbar(frame, orient="vertical", command=self._text.yview,
                             bg=COLORS["scrollbar"], troughcolor=COLORS["bg_item"],
                             relief="flat", width=8)
        self._text.configure(yscrollcommand=sb_y.set)
        self._text.pack(side="left", fill="both", expand=True)
        sb_y.pack(side="right", fill="y")

        self._text.tag_config("ok",      foreground=COLORS["success"])
        self._text.tag_config("err",     foreground=COLORS["danger"])
        self._text.tag_config("info",    foreground=COLORS["accent"])
        self._text.tag_config("warn",    foreground=COLORS["warning"])
        self._text.tag_config("muted",   foreground=COLORS["text_muted"])

    def log(self, message: str, tag: str = "info"):
        ts = datetime.now().strftime("%H:%M:%S")
        self._text.configure(state="normal")
        self._text.insert("end", f"[{ts}] {message}\n", tag)
        self._text.see("end")
        self._text.configure(state="disabled")

    def clear(self):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")


class WordToPDFApp:
    """Main application window."""

    def __init__(self):
        self.root = tk.Tk()
        self._converter = Converter()
        self._backend = detect_backend()
        self._output_dir = str(Path.home() / "Desktop")
        self._converting = False
        self._setup_window()
        self._build_ui()
        self._status_bar.set_backend(self._backend)
        self._log_startup()

    def _setup_window(self):
        self.root.title("Batch Word → PDF Converter  v2.0")
        self.root.geometry("960x700")
        self.root.minsize(800, 580)
        self.root.configure(bg=COLORS["bg"])
        # Icon (optional, won't fail if not found)
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

    def _build_ui(self):
        title_bar = tk.Frame(self.root, bg=COLORS["bg_panel"], height=60)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)

        tk.Label(title_bar,
                 text="⚡  Batch Word → PDF",
                 bg=COLORS["bg_panel"], fg=COLORS["text"],
                 font=FONTS["title"]).pack(side="left", padx=20, pady=10)

        tk.Label(title_bar,
                 text="تبدیل دسته‌ای Word به PDF",
                 bg=COLORS["bg_panel"], fg=COLORS["text_dim"],
                 font=FONTS["persian"]).pack(side="right", padx=20)

        toolbar = tk.Frame(self.root, bg=COLORS["bg"], pady=8)
        toolbar.pack(fill="x", padx=12)

        self._btn_add = RoundedButton(toolbar, "➕  افزودن فایل",
                                       command=self._add_files,
                                       width=140, height=34,
                                       bg=COLORS["accent"], hover_bg=COLORS["accent_dim"])
        self._btn_add.pack(side="left", padx=4)

        self._btn_add_folder = RoundedButton(toolbar, "📁  افزودن پوشه",
                                              command=self._add_folder,
                                              width=140, height=34,
                                              bg=COLORS["bg_panel"], hover_bg=COLORS["bg_item"])
        self._btn_add_folder.pack(side="left", padx=4)

        self._btn_remove = RoundedButton(toolbar, "🗑  حذف انتخاب",
                                          command=self._remove_selected,
                                          width=130, height=34,
                                          bg=COLORS["bg_panel"], hover_bg=COLORS["bg_item"])
        self._btn_remove.pack(side="left", padx=4)

        self._btn_clear = RoundedButton(toolbar, "🧹  پاک‌کردن همه",
                                         command=self._clear_all,
                                         width=140, height=34,
                                         bg=COLORS["bg_panel"], hover_bg=COLORS["bg_item"])
        self._btn_clear.pack(side="left", padx=4)

        sep = tk.Frame(toolbar, bg=COLORS["border"], width=1)
        sep.pack(side="left", fill="y", padx=10)

        tk.Label(toolbar, text="📂 خروجی:",
                 bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=FONTS["small"]).pack(side="left")

        self._output_var = tk.StringVar(value=self._output_dir)
        out_entry = tk.Entry(toolbar, textvariable=self._output_var,
                              width=28, bg=COLORS["bg_item"], fg=COLORS["text"],
                              insertbackground=COLORS["text"],
                              borderwidth=0, highlightthickness=1,
                              highlightbackground=COLORS["border"],
                              highlightcolor=COLORS["accent"],
                              font=FONTS["small"])
        out_entry.pack(side="left", padx=(4, 2), ipady=4)

        RoundedButton(toolbar, "…", command=self._choose_output,
                      width=32, height=28,
                      bg=COLORS["bg_item"], hover_bg=COLORS["border_light"]
                      ).pack(side="left")

        self._overwrite_var = tk.BooleanVar(value=False)
        tk.Checkbutton(toolbar, text="بازنویسی",
                       variable=self._overwrite_var,
                       bg=COLORS["bg"], fg=COLORS["text_dim"],
                       selectcolor=COLORS["bg_item"],
                       activebackground=COLORS["bg"],
                       font=FONTS["small"]).pack(side="left", padx=8)

        self._btn_convert = RoundedButton(toolbar, "▶  تبدیل",
                                           command=self._start_conversion,
                                           width=110, height=34,
                                           bg=COLORS["success"],
                                           hover_bg="#2db876")
        self._btn_convert.pack(side="right", padx=4)

        self._btn_cancel = RoundedButton(toolbar, "⏹  توقف",
                                          command=self._cancel_conversion,
                                          width=100, height=34,
                                          bg=COLORS["danger"],
                                          hover_bg=COLORS["danger_dim"])
        self._btn_cancel.pack(side="right", padx=4)

        pane = tk.PanedWindow(self.root, orient="horizontal",
                               bg=COLORS["bg"], sashwidth=6,
                               sashrelief="flat", sashpad=2)
        pane.pack(fill="both", expand=True, padx=12, pady=(0, 4))

        self._file_panel = FileListPanel(pane, on_change=self._on_file_count_change,
                                          relief="flat")
        pane.add(self._file_panel, minsize=320, stretch="always")

        right_pane = tk.Frame(pane, bg=COLORS["bg"])
        pane.add(right_pane, minsize=280, stretch="always")

        self._progress = ProgressPanel(right_pane)
        self._progress.pack(fill="x", pady=(0, 6))

        self._log = LogPanel(right_pane)
        self._log.pack(fill="both", expand=True)

        btn_row = tk.Frame(right_pane, bg=COLORS["bg"])
        btn_row.pack(fill="x", pady=4)
        RoundedButton(btn_row, "📂  باز کردن پوشه خروجی",
                       command=self._open_output_folder,
                       width=200, height=30,
                       bg=COLORS["bg_panel"], hover_bg=COLORS["bg_item"]
                       ).pack(side="right")

        self._status_bar = StatusBar(self.root)
        self._status_bar.pack(fill="x", side="bottom")


    def _log_startup(self):
        self._log.log("برنامه شروع به کار کرد", "info")
        backend_msg = {
            "libreoffice": "موتور: LibreOffice — پشتیبانی کامل از فارسی و RTL",
            "win32com":    "موتور: Microsoft Word COM Automation",
            "docx2pdf":    "موتور: docx2pdf",
            "unavailable": "⚠ هیچ موتور تبدیلی یافت نشد — LibreOffice را نصب کنید",
        }.get(self._backend, self._backend)
        tag = "warn" if self._backend == "unavailable" else "ok"
        self._log.log(backend_msg, tag)
        self._log.log(f"پوشه خروجی پیش‌فرض: {self._output_dir}", "muted")

    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="انتخاب فایل‌های Word",
            filetypes=[("Word Files", "*.docx *.doc"), ("All Files", "*.*")]
        )
        if paths:
            added = self._file_panel.add_files(list(paths))
            self._log.log(f"{added} فایل اضافه شد", "info")
            self._status_bar.set_message(f"{added} فایل اضافه شد")

    def _add_folder(self):
        folder = filedialog.askdirectory(title="انتخاب پوشه حاوی فایل‌های Word")
        if folder:
            paths = []
            for ext in ("*.docx", "*.doc"):
                from glob import glob
                paths.extend(glob(os.path.join(folder, "**", ext), recursive=True))
            added = self._file_panel.add_files(paths)
            self._log.log(f"پوشه اسکن شد: {added} فایل یافت شد", "info")

    def _remove_selected(self):
        self._file_panel.remove_selected()

    def _clear_all(self):
        if len(self._file_panel) > 0:
            if messagebox.askyesno("تأیید", "همه فایل‌ها حذف شوند؟"):
                self._file_panel.clear_all()
                self._log.log("لیست پاک شد", "muted")

    def _choose_output(self):
        folder = filedialog.askdirectory(title="انتخاب پوشه خروجی")
        if folder:
            self._output_var.set(folder)
            self._output_dir = folder
            self._log.log(f"پوشه خروجی تغییر کرد: {folder}", "muted")

    def _on_file_count_change(self, count: int):
        self._status_bar.set_message(f"{count} فایل در لیست")

    def _open_output_folder(self):
        folder = self._output_var.get()
        if not os.path.exists(folder):
            messagebox.showwarning("خطا", "پوشه خروجی وجود ندارد.")
            return
        if platform.system() == "Windows":
            os.startfile(folder)
        elif platform.system() == "Darwin":
            subprocess.run(["open", folder])
        else:
            subprocess.run(["xdg-open", folder])

    def _start_conversion(self):
        if self._converting:
            return
        files = self._file_panel.get_files()
        if not files:
            messagebox.showwarning("لیست خالی", "ابتدا فایل‌های Word اضافه کنید.")
            return

        output_dir = self._output_var.get()
        if not os.path.isdir(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("خطا", f"امکان ساخت پوشه خروجی نیست:\n{e}")
                return

        if self._backend == "unavailable":
            messagebox.showerror(
                "موتور نصب نشده",
                "LibreOffice یا Microsoft Word یافت نشد.\n\n"
                "لطفاً LibreOffice را از libreoffice.org دانلود و نصب کنید،\n"
                "سپس برنامه را مجدداً اجرا کنید."
            )
            return

        self._converting = True
        self._progress.reset()
        self._log.log("═" * 40, "muted")
        self._log.log(f"شروع تبدیل: {len(files)} فایل", "info")

        overwrite = self._overwrite_var.get()
        counter = {"i": 0, "success": 0, "failed": 0}
        import time
        start_time = [time.time()]

        def on_start(idx, total, name):
            self._file_panel.mark_converting(idx - 1)
            self._log.log(f"در حال تبدیل: {name}", "info")

        def on_done(result: ConversionResult):
            i = counter["i"]
            self._file_panel.mark_done(i, result.success)
            if result.success:
                counter["success"] += 1
                self._log.log(
                    f"✅ {Path(result.source).name}  →  {result.file_size_kb:.0f} KB  "
                    f"({result.duration:.1f}s)", "ok"
                )
            else:
                counter["failed"] += 1
                self._log.log(f"❌ {Path(result.source).name}: {result.error}", "err")
            counter["i"] += 1
            elapsed = time.time() - start_time[0]
            self._progress.update(counter["i"], len(files),
                                   counter["success"], counter["failed"], elapsed)

        def on_finish(stats: ConversionStats):
            self._converting = False
            self._log.log("═" * 40, "muted")
            self._log.log(
                f"تمام شد!  موفق: {stats.success}  |  خطا: {stats.failed}  "
                f"|  زمان کل: {stats.total_time:.1f}s", "ok"
            )
            self._status_bar.set_message(
                f"تبدیل تمام شد: {stats.success}/{stats.total} موفق"
            )
            if stats.failed > 0:
                self.root.after(0, lambda: messagebox.showwarning(
                    "نتیجه تبدیل",
                    f"تبدیل کامل شد.\n\n"
                    f"✅ موفق: {stats.success}\n"
                    f"❌ خطا: {stats.failed}\n\n"
                    "جزئیات در پنل گزارش قابل مشاهده است."
                ))

        def run():
            self._converter.convert_batch(
                files, output_dir, overwrite,
                on_start=lambda i, t, n: self.root.after(0, lambda: on_start(i, t, n)),
                on_done=lambda r: self.root.after(0, lambda: on_done(r)),
                on_finish=lambda s: self.root.after(0, lambda: on_finish(s)),
            )

        threading.Thread(target=run, daemon=True).start()

    def _cancel_conversion(self):
        if self._converting:
            self._converter.cancel()
            self._log.log("⏹ توقف توسط کاربر", "warn")
            self._status_bar.set_message("تبدیل متوقف شد")
            self._converting = False

    def run(self):
        self.root.mainloop()
