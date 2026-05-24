import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
import subprocess
import platform
import time
from pathlib import Path
from datetime import datetime
from glob import glob

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.converter import Converter, ConversionResult, ConversionStats, detect_backend
from core.compressor import (
    Compressor, CompressionResult, CompressionStats,
    detect_compression_backend, QUALITY_LABELS
)

C = {
    "bg":           "#080c14",
    "bg2":          "#0d1220",
    "bg3":          "#111827",
    "surface":      "#141d2e",
    "surface2":     "#1a2540",
    "surface3":     "#1f2d4a",
    "border":       "#1e2d47",
    "border2":      "#263552",
    "accent":       "#00d4ff",
    "accent2":      "#0099cc",
    "accent3":      "#004466",
    "green":        "#00ff9d",
    "green2":       "#00c87a",
    "green_dim":    "#003322",
    "red":          "#ff3d6b",
    "red2":         "#cc1f47",
    "red_dim":      "#330010",
    "yellow":       "#ffcc00",
    "yellow_dim":   "#332800",
    "purple":       "#a855f7",
    "purple_dim":   "#1e0a33",
    "orange":       "#ff8c00",
    "orange2":      "#cc6600",
    "orange_dim":   "#331a00",
    "text":         "#e2e8f4",
    "text2":        "#94a3c4",
    "text3":        "#4a5a7a",
    "text4":        "#2a3a5a",
    "white":        "#ffffff",
}

F = {
    "title":  ("Segoe UI", 20, "bold"),
    "h1":     ("Segoe UI", 14, "bold"),
    "h2":     ("Segoe UI", 11, "bold"),
    "body":   ("Segoe UI", 10),
    "small":  ("Segoe UI", 9),
    "tiny":   ("Segoe UI", 8),
    "mono":   ("Cascadia Code", 9),
    "mono2":  ("Consolas", 9),
    "fa":     ("Tahoma", 10),
    "fa_big": ("Tahoma", 13, "bold"),
}


class GlowButton(tk.Canvas):
    def __init__(self, parent, text, command=None,
                 w=130, h=38, bg=None, fg=None,
                 hover=None, radius=10, font=None, **kw):
        # Resolve parent background robustly
        try:
            parent_bg = parent.cget("bg")
        except Exception:
            parent_bg = C["bg"]
        kw.setdefault("bg", parent_bg)
        super().__init__(parent, width=w, height=h,
                         highlightthickness=0, **kw)
        self._bg      = bg    or C["accent2"]
        self._hover   = hover or C["accent"]
        self._fg      = fg    or C["white"]
        self._text    = text
        self._cmd     = command
        self._r       = radius
        self._font    = font  or F["body"]
        self._width, self._height = w, h
        self._enabled = True
        self._ready   = False
        self.after(0, self._initial_draw)
        self.bind("<Enter>",    lambda e: self._on_enter())
        self.bind("<Leave>",    lambda e: self._on_leave())
        self.bind("<Button-1>", lambda e: self._on_click())

    def _initial_draw(self):
        self._ready = True
        self._draw(self._bg)

    def _rounded_rect(self, x1, y1, x2, y2, r, **kw):
        self.create_arc(x1,      y1,      x1+2*r, y1+2*r, start=90,  extent=90,  **kw)
        self.create_arc(x2-2*r,  y1,      x2,     y1+2*r, start=0,   extent=90,  **kw)
        self.create_arc(x1,      y2-2*r,  x1+2*r, y2,     start=180, extent=90,  **kw)
        self.create_arc(x2-2*r,  y2-2*r,  x2,     y2,     start=270, extent=90,  **kw)
        self.create_rectangle(x1+r, y1,   x2-r, y2, **kw)
        self.create_rectangle(x1,   y1+r, x2,   y2-r, **kw)

    def _draw(self, color, glow=False):
        if not self._ready:
            return
        self.delete("all")
        w, h, r = self._width, self._height, self._r
        if glow:
            for i in range(4, 0, -1):
                self._rounded_rect(i, i, w-i, h-i, r+1,
                                   fill="", outline=color, width=1)
        self._rounded_rect(2, 2, w-2, h-2, r, fill=color, outline=color)
        self.create_text(w//2, h//2, text=self._text,
                         fill=self._fg, font=self._font, anchor="center")

    def _on_enter(self):
        if self._enabled:
            self._draw(self._hover, glow=True)
            self.config(cursor="hand2")

    def _on_leave(self):
        if self._enabled:
            self._draw(self._bg)
            self.config(cursor="")

    def _on_click(self):
        if self._enabled and self._cmd:
            self._draw(self._hover)
            self.after(80, lambda: self._draw(self._bg))
            self._cmd()

    def set_enabled(self, v: bool):
        self._enabled = v
        if v:
            self._draw(self._bg)
            self.bind("<Button-1>", lambda e: self._on_click())
        else:
            self._draw(C["surface2"])
            self.unbind("<Button-1>")

    def set_text(self, t: str):
        self._text = t
        self._draw(self._bg)


class VSep(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, width=1, bg=C["border2"], **kw)


class HSep(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, height=1, bg=C["border2"], **kw)


class StatCard(tk.Frame):
    def __init__(self, parent, icon, label, color, **kw):
        super().__init__(parent, bg=C["surface"], **kw)
        inner = tk.Frame(self, bg=C["surface"], padx=14, pady=10)
        inner.pack(fill="both", expand=True)
        top = tk.Frame(inner, bg=C["surface"])
        top.pack(fill="x")
        tk.Label(top, text=icon, bg=C["surface"],
                 fg=color, font=F["h1"]).pack(side="left")
        tk.Label(top, text=label, bg=C["surface"],
                 fg=C["text3"], font=F["tiny"]).pack(side="right", pady=(4, 0))
        self._val = tk.Label(inner, text="—", bg=C["surface"],
                             fg=color, font=("Segoe UI", 22, "bold"))
        self._val.pack(anchor="w", pady=(2, 0))
        tk.Frame(self, height=2, bg=color).pack(fill="x", side="bottom")

    def set(self, v: str):
        self._val.config(text=v)


class AnimatedProgressBar(tk.Canvas):
    def __init__(self, parent, h=6, **kw):
        super().__init__(parent, height=h, bg=C["surface"],
                         highlightthickness=0, **kw)
        self._pct = 0
        self._h = h
        self._color = C["accent2"]
        self.bind("<Configure>", lambda e: self._draw())

    def set_color(self, color: str):
        self._color = color

    def set_progress(self, pct: int):
        self._pct = max(0, min(100, pct))
        self._draw()

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self._h
        if w < 4:
            return
        self.create_rectangle(0, 0, w, h, fill=C["surface3"], outline="")
        fill_w = int(w * self._pct / 100)
        if fill_w > 2:
            self.create_rectangle(0, 0, fill_w, h, fill=self._color, outline="")
            self.create_rectangle(0, 0, fill_w, h//2, fill=C["accent"], outline="")
            if fill_w > 8:
                self.create_rectangle(fill_w-6, 0, fill_w, h,
                                      fill=C["accent"], outline="")


class FileRow(tk.Frame):
    STATUS_COLORS = {
        "idle":       C["text2"],
        "converting": C["yellow"],
        "done":       C["green"],
        "error":      C["red"],
    }
    STATUS_ICONS = {
        "idle":       "○",
        "converting": "◉",
        "done":       "✓",
        "error":      "✗",
    }

    def __init__(self, parent, path: str, index: int, ext_filter=None, **kw):
        super().__init__(parent, bg=C["surface"] if index % 2 == 0 else C["surface2"],
                         cursor="hand2", **kw)
        self._path = path
        self._status = "idle"
        self._base_bg = self["bg"]
        self._ext_filter = ext_filter
        self._build()
        self.bind("<Enter>", lambda e: self.config(bg=C["surface3"]))
        self.bind("<Leave>", lambda e: self.config(bg=self._base_bg))

    def _build(self):
        pad = tk.Frame(self, bg=self["bg"], height=38)
        pad.pack(fill="x")
        pad.pack_propagate(False)

        self._dot = tk.Label(pad, text="○", bg=self["bg"],
                             fg=C["text3"], font=("Segoe UI", 12, "bold"), width=2)
        self._dot.pack(side="left", padx=(10, 4))

        stem = Path(self._path).stem
        ext  = Path(self._path).suffix.upper().lstrip(".")

        name_frame = tk.Frame(pad, bg=self["bg"])
        name_frame.pack(side="left", fill="x", expand=True)

        display = stem[:38] + ("…" if len(stem) > 38 else "")
        tk.Label(name_frame, text=display, bg=self["bg"],
                 fg=C["text"], font=F["body"], anchor="w").pack(anchor="w")

        try:
            size_kb = os.path.getsize(self._path) / 1024
            size_str = f"{size_kb:.0f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
        except Exception:
            size_str = "—"

        meta_frame = tk.Frame(name_frame, bg=self["bg"])
        meta_frame.pack(anchor="w")

        badge_color = C["accent3"] if ext in ("DOCX", "DOC") else C["orange_dim"]
        badge_fg    = C["accent"]  if ext in ("DOCX", "DOC") else C["orange"]
        tk.Label(meta_frame, text=f" {ext} ",
                 bg=badge_color, fg=badge_fg,
                 font=F["tiny"], relief="flat").pack(side="left", padx=(0, 6))
        tk.Label(meta_frame, text=size_str, bg=self["bg"],
                 fg=C["text3"], font=F["tiny"]).pack(side="left")

        self._dur_label = tk.Label(pad, text="", bg=self["bg"],
                                   fg=C["text3"], font=F["tiny"])
        self._dur_label.pack(side="right", padx=(0, 12))

    def set_status(self, status: str, duration: float = 0, extra: str = ""):
        self._status = status
        color = self.STATUS_COLORS.get(status, C["text2"])
        icon  = self.STATUS_ICONS.get(status, "○")
        self._dot.config(text=icon, fg=color)
        label = ""
        if duration > 0:
            label = f"{duration:.1f}s"
        if extra:
            label = extra if not label else f"{label}  {extra}"
        if label:
            self._dur_label.config(text=label, fg=C["text3"])
        flash = {"done": C["green_dim"], "error": C["red_dim"],
                 "converting": C["yellow_dim"]}.get(status)
        if flash:
            self.config(bg=flash)
            self.after(600, lambda: self.config(bg=self._base_bg))


class FileListPanel(tk.Frame):
    def __init__(self, parent, on_change=None, ext_filter=(".doc", ".docx"), **kw):
        super().__init__(parent, bg=C["bg3"], **kw)
        self._on_change  = on_change
        self._ext_filter = ext_filter
        self._files: list[str] = []
        self._rows:  list[FileRow] = []
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=C["surface"], height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="FILES", bg=C["surface"],
                 fg=C["accent"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=16, pady=12)
        self._count_lbl = tk.Label(hdr, text="empty", bg=C["surface"],
                                   fg=C["text3"], font=F["small"])
        self._count_lbl.pack(side="right", padx=16)
        HSep(self).pack(fill="x")

        self._canvas = tk.Canvas(self, bg=C["bg3"], highlightthickness=0, borderwidth=0)
        self._scrollbar = tk.Scrollbar(self, orient="vertical",
                                        command=self._canvas.yview,
                                        bg=C["bg3"], troughcolor=C["bg3"],
                                        relief="flat", width=6)
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=C["bg3"])
        self._canvas_window = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")

        self._empty = tk.Frame(self._canvas, bg=C["bg3"])
        self._empty_win = self._canvas.create_window((0, 0), window=self._empty, anchor="nw")
        self._build_empty()
        self._show_empty(True)

        self._inner.bind("<Configure>", lambda e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._inner.bind("<MouseWheel>", self._on_mousewheel)

    def _build_empty(self):
        frame = tk.Frame(self._empty, bg=C["bg3"])
        frame.place(relx=0.5, rely=0.45, anchor="center")
        ext_str = "/".join(e.upper().lstrip(".") for e in self._ext_filter)
        tk.Label(frame, text="⬡", bg=C["bg3"],
                 fg=C["border2"], font=("Segoe UI", 48)).pack()
        tk.Label(frame, text=f"Drop {ext_str} files here", bg=C["bg3"],
                 fg=C["text3"], font=F["h2"]).pack(pady=(4, 2))
        tk.Label(frame, text="or use the Add File / Add Folder buttons above",
                 bg=C["bg3"], fg=C["text4"], font=F["small"]).pack()

    def _show_empty(self, show: bool):
        if show:
            self._canvas.itemconfigure(self._empty_win, state="normal")
            self._canvas.itemconfigure(self._canvas_window, state="hidden")
        else:
            self._canvas.itemconfigure(self._empty_win, state="hidden")
            self._canvas.itemconfigure(self._canvas_window, state="normal")

    def _on_canvas_configure(self, e):
        self._canvas.itemconfig(self._canvas_window, width=e.width)
        self._canvas.itemconfig(self._empty_win, width=e.width)
        self._empty.config(height=self._canvas.winfo_height())

    def _on_mousewheel(self, e):
        self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    def add_files(self, paths: list[str]) -> int:
        existing = set(self._files)
        added = 0
        for p in paths:
            if p not in existing and p.lower().endswith(self._ext_filter):
                idx = len(self._files)
                self._files.append(p)
                row = FileRow(self._inner, p, idx)
                row.pack(fill="x")
                row.bind("<MouseWheel>", self._on_mousewheel)
                self._rows.append(row)
                added += 1
        self._refresh()
        return added

    def clear_all(self):
        for row in self._rows:
            row.destroy()
        self._files.clear()
        self._rows.clear()
        self._refresh()

    def get_files(self) -> list[str]:
        return list(self._files)

    def mark_converting(self, idx: int):
        if 0 <= idx < len(self._rows):
            self._rows[idx].set_status("converting")
            self._canvas.yview_moveto(idx / max(len(self._rows), 1))

    def mark_done(self, idx: int, success: bool, duration: float = 0, extra: str = ""):
        if 0 <= idx < len(self._rows):
            self._rows[idx].set_status("done" if success else "error", duration, extra)

    def _refresh(self):
        n = len(self._files)
        self._count_lbl.config(text="empty" if n == 0 else f"{n} file{'s' if n != 1 else ''}")
        self._show_empty(n == 0)
        if self._on_change:
            self._on_change(n)

    def __len__(self):
        return len(self._files)


class LogPanel(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=C["bg3"], **kw)
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=C["surface"], height=36)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="ACTIVITY LOG", bg=C["surface"],
                 fg=C["accent"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=16, pady=8)
        clr = tk.Label(hdr, text="clear", bg=C["surface"],
                       fg=C["text3"], font=F["small"], cursor="hand2")
        clr.pack(side="right", padx=16)
        clr.bind("<Button-1>", lambda e: self.clear())
        HSep(self).pack(fill="x")

        mono_font = F["mono"]
        try:
            tk.Label(self, font=F["mono"]).destroy()
        except Exception:
            mono_font = F["mono2"]

        self._text = tk.Text(self, bg=C["bg3"], fg=C["text2"],
                             font=mono_font, borderwidth=0,
                             highlightthickness=0, state="disabled",
                             wrap="none", padx=12, pady=8,
                             insertbackground=C["text"],
                             selectbackground=C["surface3"])
        sb = tk.Scrollbar(self, orient="vertical", command=self._text.yview,
                          bg=C["bg3"], troughcolor=C["bg3"], relief="flat", width=6)
        self._text.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._text.pack(fill="both", expand=True)

        self._text.tag_config("ok",    foreground=C["green"])
        self._text.tag_config("err",   foreground=C["red"])
        self._text.tag_config("info",  foreground=C["accent"])
        self._text.tag_config("warn",  foreground=C["yellow"])
        self._text.tag_config("muted", foreground=C["text4"])
        self._text.tag_config("ts",    foreground=C["text4"])

    def log(self, msg: str, tag: str = "info"):
        ts = datetime.now().strftime("%H:%M:%S")
        self._text.config(state="normal")
        self._text.insert("end", f"[{ts}] ", "ts")
        self._text.insert("end", f"{msg}\n", tag)
        self._text.see("end")
        self._text.config(state="disabled")

    def clear(self):
        self._text.config(state="normal")
        self._text.delete("1.0", "end")
        self._text.config(state="disabled")


class ConversionTab(tk.Frame):
    def __init__(self, parent, status_callback, **kw):
        super().__init__(parent, bg=C["bg"], **kw)
        self._status_cb   = status_callback
        self._converter   = Converter()
        self._backend     = detect_backend()
        self._output_dir  = str(Path.home() / "Desktop")
        self._converting  = False
        self._overwrite_var = tk.BooleanVar(value=False)
        self._output_var    = tk.StringVar(value=self._output_dir)
        self._build()

    def _build(self):
        self._build_toolbar()
        HSep(self).pack(fill="x")
        self._build_main()

    def _build_toolbar(self):
        tb = tk.Frame(self, bg=C["bg"], pady=10)
        tb.pack(fill="x", padx=16)

        GlowButton(tb, "＋  Add Files", command=self._add_files,
                   w=130, h=36, bg=C["accent2"], hover=C["accent"],
                   fg=C["white"]).pack(side="left", padx=(0, 6))
        GlowButton(tb, "⊞  Add Folder", command=self._add_folder,
                   w=130, h=36, bg=C["surface2"], hover=C["surface3"],
                   fg=C["text"]).pack(side="left", padx=(0, 6))
        GlowButton(tb, "✕  Remove", command=self._remove_last,
                   w=100, h=36, bg=C["surface2"], hover=C["surface3"],
                   fg=C["text"]).pack(side="left", padx=(0, 6))
        GlowButton(tb, "⌫  Clear All", command=self._clear_all,
                   w=105, h=36, bg=C["surface2"], hover=C["surface3"],
                   fg=C["text"]).pack(side="left", padx=(0, 16))

        VSep(tb).pack(side="left", fill="y", pady=4, padx=6)

        tk.Label(tb, text="Output", bg=C["bg"],
                 fg=C["text3"], font=F["small"]).pack(side="left", padx=(8, 6))
        tk.Entry(tb, textvariable=self._output_var,
                 width=28, bg=C["surface"], fg=C["text"],
                 insertbackground=C["text"], borderwidth=0,
                 highlightthickness=1,
                 highlightbackground=C["border2"],
                 highlightcolor=C["accent"],
                 font=F["small"], relief="flat").pack(side="left", ipady=6, padx=(0, 4))
        GlowButton(tb, "…", command=self._choose_output,
                   w=36, h=36, bg=C["surface2"], hover=C["surface3"],
                   fg=C["text"]).pack(side="left", padx=(0, 16))

        ow_frame = tk.Frame(tb, bg=C["bg"])
        ow_frame.pack(side="left", padx=(0, 16))
        self._ow_indicator = tk.Label(ow_frame, text="○",
                                       bg=C["bg"], fg=C["text3"],
                                       font=F["body"], cursor="hand2")
        self._ow_indicator.pack(side="left")
        ow_lbl = tk.Label(ow_frame, text=" Overwrite",
                          bg=C["bg"], fg=C["text3"], font=F["small"], cursor="hand2")
        ow_lbl.pack(side="left")
        for w in (self._ow_indicator, ow_lbl):
            w.bind("<Button-1>", lambda e: self._toggle_overwrite())

        VSep(tb).pack(side="left", fill="y", pady=4, padx=6)

        self._btn_convert = GlowButton(tb, "▶  Convert",
                                        command=self._start_conversion,
                                        w=120, h=36,
                                        bg=C["green2"], hover=C["green"],
                                        fg=C["bg"])
        self._btn_convert.pack(side="right", padx=(6, 0))

        GlowButton(tb, "■  Stop", command=self._cancel_conversion,
                   w=95, h=36, bg=C["red2"], hover=C["red"],
                   fg=C["white"]).pack(side="right", padx=6)

    def _toggle_overwrite(self):
        v = not self._overwrite_var.get()
        self._overwrite_var.set(v)
        self._ow_indicator.config(text="●" if v else "○",
                                   fg=C["accent"] if v else C["text3"])

    def _build_main(self):
        main = tk.Frame(self, bg=C["bg"])
        main.pack(fill="both", expand=True)

        left = tk.Frame(main, bg=C["bg"])
        left.pack(side="left", fill="both", expand=True)
        self._file_panel = FileListPanel(left, on_change=self._on_file_count_change,
                                          ext_filter=(".doc", ".docx"))
        self._file_panel.pack(fill="both", expand=True)

        VSep(main).pack(side="left", fill="y")

        right = tk.Frame(main, bg=C["bg"], width=440)
        right.pack(side="right", fill="both")
        right.pack_propagate(False)

        self._build_stats_row(right)
        HSep(right).pack(fill="x")
        self._build_progress_section(right)
        HSep(right).pack(fill="x")
        self._log = LogPanel(right)
        self._log.pack(fill="both", expand=True)
        HSep(right).pack(fill="x")
        self._build_bottom_bar(right)

    def _build_stats_row(self, parent):
        row = tk.Frame(parent, bg=C["bg"], pady=12)
        row.pack(fill="x", padx=12)
        cards = [
            ("✓", "SUCCESS", C["green"]),
            ("✗", "FAILED",  C["red"]),
            ("⚡", "SPEED",  C["yellow"]),
            ("⏱", "ELAPSED", C["purple"]),
        ]
        self._stat_cards = {}
        for icon, lbl, color in cards:
            card = StatCard(row, icon, lbl, color)
            card.pack(side="left", fill="x", expand=True, padx=3)
            self._stat_cards[lbl] = card

    def _build_progress_section(self, parent):
        sec = tk.Frame(parent, bg=C["bg"], padx=12, pady=10)
        sec.pack(fill="x")
        top = tk.Frame(sec, bg=C["bg"])
        top.pack(fill="x", pady=(0, 6))
        tk.Label(top, text="PROGRESS", bg=C["bg"],
                 fg=C["accent"], font=("Segoe UI", 9, "bold")).pack(side="left")
        self._pct_label = tk.Label(top, text="—", bg=C["bg"],
                                   fg=C["text2"], font=F["small"])
        self._pct_label.pack(side="right")
        self._progress_bar = AnimatedProgressBar(sec, h=8)
        self._progress_bar.pack(fill="x")
        self._progress_detail = tk.Label(sec, text="Waiting…",
                                          bg=C["bg"], fg=C["text3"],
                                          font=F["small"], anchor="w")
        self._progress_detail.pack(fill="x", pady=(4, 0))

    def _build_bottom_bar(self, parent):
        bar = tk.Frame(parent, bg=C["surface"], height=38)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        GlowButton(bar, "📂 Open Output", command=self._open_output,
                   w=150, h=30, bg=C["surface2"], hover=C["surface3"],
                   fg=C["text"]).pack(side="right", padx=10, pady=4)

    def _update_stats(self, success, failed, elapsed, current, total):
        self._stat_cards["SUCCESS"].set(str(success))
        self._stat_cards["FAILED"].set(str(failed))
        speed = current / elapsed if elapsed > 0 else 0
        self._stat_cards["SPEED"].set(f"{speed:.1f}/s")
        self._stat_cards["ELAPSED"].set(f"{elapsed:.0f}s")
        pct = int(current / total * 100) if total > 0 else 0
        self._progress_bar.set_progress(pct)
        self._pct_label.config(text=f"{pct}%")
        self._progress_detail.config(text=f"{current} of {total} files converted")

    def _reset_stats(self):
        for card in self._stat_cards.values():
            card.set("—")
        self._progress_bar.set_progress(0)
        self._pct_label.config(text="—")
        self._progress_detail.config(text="Waiting…")

    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="Select Word Files",
            filetypes=[("Word Files", "*.docx *.doc"), ("All Files", "*.*")]
        )
        if paths:
            added = self._file_panel.add_files(list(paths))
            self._log.log(f"{added} file(s) added", "info")
            self._status_cb(f"{added} files added")

    def _add_folder(self):
        folder = filedialog.askdirectory(title="Select Folder with Word Files")
        if folder:
            paths = []
            for ext in ("*.docx", "*.doc"):
                paths.extend(glob(os.path.join(folder, "**", ext), recursive=True))
            added = self._file_panel.add_files(paths)
            self._log.log(f"Folder scanned — {added} file(s) found", "info")

    def _remove_last(self):
        rows = self._file_panel._rows
        files = self._file_panel._files
        if rows:
            rows[-1].destroy()
            rows.pop()
            files.pop()
            self._file_panel._refresh()

    def _clear_all(self):
        if len(self._file_panel.get_files()) > 0:
            if messagebox.askyesno("Clear All", "Remove all files from the list?"):
                self._file_panel.clear_all()
                self._log.log("File list cleared", "muted")

    def _choose_output(self):
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self._output_var.set(folder)
            self._output_dir = folder
            self._log.log(f"Output: {folder}", "muted")

    def _on_file_count_change(self, count: int):
        self._status_cb(f"{count} file(s) in queue")

    def _open_output(self):
        folder = self._output_var.get()
        if not os.path.exists(folder):
            messagebox.showwarning("Error", "Output folder doesn't exist.")
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
            messagebox.showwarning("Empty Queue", "Add Word files first.")
            return
        output_dir = self._output_var.get()
        os.makedirs(output_dir, exist_ok=True)
        if self._backend == "unavailable":
            messagebox.showerror("No Conversion Engine",
                                 "LibreOffice or Microsoft Word not found.\n\n"
                                 "Download LibreOffice from libreoffice.org and restart.")
            return

        self._converting = True
        self._reset_stats()
        self._log.log("━" * 36, "muted")
        self._log.log(f"Starting conversion: {len(files)} file(s)", "info")
        self._status_cb("Converting…")
        self._btn_convert.set_text("◉  Running")

        overwrite = self._overwrite_var.get()
        counter = {"i": 0, "success": 0, "failed": 0}
        t0 = [time.time()]

        def on_start(idx, total, name):
            self._file_panel.mark_converting(idx - 1)
            self._log.log(f"Converting: {name}", "info")

        def on_done(result: ConversionResult):
            i = counter["i"]
            self._file_panel.mark_done(i, result.success, result.duration)
            if result.success:
                counter["success"] += 1
                self._log.log(f"✓ {Path(result.source).name}"
                              f"  →  {result.file_size_kb:.0f} KB"
                              f"  ({result.duration:.1f}s)", "ok")
            else:
                counter["failed"] += 1
                self._log.log(f"✗ {Path(result.source).name}: {result.error}", "err")
            counter["i"] += 1
            elapsed = time.time() - t0[0]
            self._update_stats(counter["success"], counter["failed"],
                               elapsed, counter["i"], len(files))

        def on_finish(stats: ConversionStats):
            self._converting = False
            self._log.log("━" * 36, "muted")
            self._log.log(f"Done!  ✓ {stats.success}  ✗ {stats.failed}"
                          f"  |  {stats.total_time:.1f}s total", "ok")
            self._status_cb(f"Finished: {stats.success}/{stats.total} converted")
            self._btn_convert.set_text("▶  Convert")
            if stats.failed > 0:
                self.after(0, lambda: messagebox.showwarning(
                    "Conversion Complete",
                    f"✓ Success: {stats.success}\n✗ Failed: {stats.failed}\n\n"
                    "See the activity log for details."
                ))

        def run():
            self._converter.convert_batch(
                files, output_dir, overwrite,
                on_start=lambda i, t, n: self.after(0, lambda: on_start(i, t, n)),
                on_done=lambda r: self.after(0, lambda: on_done(r)),
                on_finish=lambda s: self.after(0, lambda: on_finish(s)),
            )

        threading.Thread(target=run, daemon=True).start()

    def _cancel_conversion(self):
        if self._converting:
            self._converter.cancel()
            self._converting = False
            self._log.log("Conversion stopped by user", "warn")
            self._status_cb("Stopped")
            self._btn_convert.set_text("▶  Convert")


class CompressionTab(tk.Frame):
    def __init__(self, parent, status_callback, **kw):
        super().__init__(parent, bg=C["bg"], **kw)
        self._status_cb   = status_callback
        self._compressor  = Compressor()
        self._comp_backend = detect_compression_backend()
        self._output_dir  = str(Path.home() / "Desktop")
        self._compressing = False
        self._output_var  = tk.StringVar(value=self._output_dir)
        self._quality_var = tk.StringVar(value="ebook")
        self._overwrite_var = tk.BooleanVar(value=False)
        self._build()

    def _build(self):
        self._build_toolbar()
        HSep(self).pack(fill="x")
        self._build_main()

    def _build_toolbar(self):
        tb = tk.Frame(self, bg=C["bg"], pady=10)
        tb.pack(fill="x", padx=16)

        GlowButton(tb, "＋  Add PDFs", command=self._add_files,
                   w=130, h=36, bg=C["orange2"], hover=C["orange"],
                   fg=C["white"]).pack(side="left", padx=(0, 6))
        GlowButton(tb, "⊞  Add Folder", command=self._add_folder,
                   w=130, h=36, bg=C["surface2"], hover=C["surface3"],
                   fg=C["text"]).pack(side="left", padx=(0, 6))
        GlowButton(tb, "✕  Remove", command=self._remove_last,
                   w=100, h=36, bg=C["surface2"], hover=C["surface3"],
                   fg=C["text"]).pack(side="left", padx=(0, 6))
        GlowButton(tb, "⌫  Clear All", command=self._clear_all,
                   w=105, h=36, bg=C["surface2"], hover=C["surface3"],
                   fg=C["text"]).pack(side="left", padx=(0, 16))

        VSep(tb).pack(side="left", fill="y", pady=4, padx=6)

        tk.Label(tb, text="Quality", bg=C["bg"],
                 fg=C["text3"], font=F["small"]).pack(side="left", padx=(8, 6))

        quality_menu = tk.OptionMenu(tb, self._quality_var,
                                     *QUALITY_LABELS.keys())
        quality_menu.config(bg=C["surface2"], fg=C["text"],
                             activebackground=C["surface3"],
                             activeforeground=C["text"],
                             font=F["small"], borderwidth=0,
                             highlightthickness=0, relief="flat",
                             indicatoron=True, width=10)
        quality_menu["menu"].config(bg=C["surface2"], fg=C["text"],
                                    activebackground=C["surface3"],
                                    activeforeground=C["text"],
                                    font=F["small"], borderwidth=0)
        quality_menu.pack(side="left", padx=(0, 12))

        VSep(tb).pack(side="left", fill="y", pady=4, padx=6)

        tk.Label(tb, text="Output", bg=C["bg"],
                 fg=C["text3"], font=F["small"]).pack(side="left", padx=(8, 6))
        tk.Entry(tb, textvariable=self._output_var,
                 width=24, bg=C["surface"], fg=C["text"],
                 insertbackground=C["text"], borderwidth=0,
                 highlightthickness=1,
                 highlightbackground=C["border2"],
                 highlightcolor=C["orange"],
                 font=F["small"], relief="flat").pack(side="left", ipady=6, padx=(0, 4))
        GlowButton(tb, "…", command=self._choose_output,
                   w=36, h=36, bg=C["surface2"], hover=C["surface3"],
                   fg=C["text"]).pack(side="left", padx=(0, 16))

        ow_frame = tk.Frame(tb, bg=C["bg"])
        ow_frame.pack(side="left", padx=(0, 16))
        self._ow_indicator = tk.Label(ow_frame, text="○",
                                       bg=C["bg"], fg=C["text3"],
                                       font=F["body"], cursor="hand2")
        self._ow_indicator.pack(side="left")
        ow_lbl = tk.Label(ow_frame, text=" Overwrite",
                          bg=C["bg"], fg=C["text3"], font=F["small"], cursor="hand2")
        ow_lbl.pack(side="left")
        for w in (self._ow_indicator, ow_lbl):
            w.bind("<Button-1>", lambda e: self._toggle_overwrite())

        VSep(tb).pack(side="left", fill="y", pady=4, padx=6)

        self._btn_compress = GlowButton(tb, "⚙  Compress",
                                         command=self._start_compression,
                                         w=125, h=36,
                                         bg=C["orange2"], hover=C["orange"],
                                         fg=C["white"])
        self._btn_compress.pack(side="right", padx=(6, 0))

        GlowButton(tb, "■  Stop", command=self._cancel_compression,
                   w=95, h=36, bg=C["red2"], hover=C["red"],
                   fg=C["white"]).pack(side="right", padx=6)

    def _toggle_overwrite(self):
        v = not self._overwrite_var.get()
        self._overwrite_var.set(v)
        self._ow_indicator.config(text="●" if v else "○",
                                   fg=C["orange"] if v else C["text3"])

    def _build_main(self):
        main = tk.Frame(self, bg=C["bg"])
        main.pack(fill="both", expand=True)

        # Warning banner if no compression engine
        if self._comp_backend == "unavailable":
            warn = tk.Frame(main, bg=C["orange_dim"], pady=8)
            warn.pack(fill="x", padx=0)
            tk.Label(warn,
                     text="⚠  No compression engine found.  Run:  pip install pypdf",
                     bg=C["orange_dim"], fg=C["orange"],
                     font=("Segoe UI", 10, "bold")).pack(side="left", padx=16)

        left = tk.Frame(main, bg=C["bg"])
        left.pack(side="left", fill="both", expand=True)
        self._file_panel = FileListPanel(left, on_change=self._on_file_count_change,
                                          ext_filter=(".pdf",))
        self._file_panel.pack(fill="both", expand=True)

        VSep(main).pack(side="left", fill="y")

        right = tk.Frame(main, bg=C["bg"], width=440)
        right.pack(side="right", fill="both")
        right.pack_propagate(False)

        self._build_stats_row(right)
        HSep(right).pack(fill="x")
        self._build_progress_section(right)
        HSep(right).pack(fill="x")
        self._log = LogPanel(right)
        self._log.pack(fill="both", expand=True)
        HSep(right).pack(fill="x")
        self._build_bottom_bar(right)

    def _build_stats_row(self, parent):
        row = tk.Frame(parent, bg=C["bg"], pady=12)
        row.pack(fill="x", padx=12)
        cards = [
            ("✓", "SUCCESS", C["green"]),
            ("✗", "FAILED",  C["red"]),
            ("💾", "SAVED",  C["orange"]),
            ("⏱", "ELAPSED", C["purple"]),
        ]
        self._stat_cards = {}
        for icon, lbl, color in cards:
            card = StatCard(row, icon, lbl, color)
            card.pack(side="left", fill="x", expand=True, padx=3)
            self._stat_cards[lbl] = card

    def _build_progress_section(self, parent):
        sec = tk.Frame(parent, bg=C["bg"], padx=12, pady=10)
        sec.pack(fill="x")
        top = tk.Frame(sec, bg=C["bg"])
        top.pack(fill="x", pady=(0, 6))
        tk.Label(top, text="PROGRESS", bg=C["bg"],
                 fg=C["orange"], font=("Segoe UI", 9, "bold")).pack(side="left")
        self._pct_label = tk.Label(top, text="—", bg=C["bg"],
                                   fg=C["text2"], font=F["small"])
        self._pct_label.pack(side="right")
        self._progress_bar = AnimatedProgressBar(sec, h=8)
        self._progress_bar.set_color(C["orange2"])
        self._progress_bar.pack(fill="x")
        self._progress_detail = tk.Label(sec, text="Waiting…",
                                          bg=C["bg"], fg=C["text3"],
                                          font=F["small"], anchor="w")
        self._progress_detail.pack(fill="x", pady=(4, 0))

    def _build_bottom_bar(self, parent):
        bar = tk.Frame(parent, bg=C["surface"], height=38)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        bname = {
            "ghostscript": "Ghostscript",
            "pikepdf":     "pikepdf",
            "pypdf":       "pypdf / PyPDF2",
            "unavailable": "⚠ No Engine",
        }.get(self._comp_backend, self._comp_backend)
        bc = C["green"] if self._comp_backend != "unavailable" else C["red"]
        tk.Label(bar, text=f"Engine: {bname}", bg=C["surface"],
                 fg=bc, font=F["tiny"]).pack(side="left", padx=14)

        GlowButton(bar, "📂 Open Output", command=self._open_output,
                   w=150, h=30, bg=C["surface2"], hover=C["surface3"],
                   fg=C["text"]).pack(side="right", padx=10, pady=4)

    def _update_stats(self, success, failed, elapsed, current, total, saved_kb):
        self._stat_cards["SUCCESS"].set(str(success))
        self._stat_cards["FAILED"].set(str(failed))
        saved_str = f"{saved_kb/1024:.1f} MB" if saved_kb >= 1024 else f"{saved_kb:.0f} KB"
        self._stat_cards["SAVED"].set(saved_str)
        self._stat_cards["ELAPSED"].set(f"{elapsed:.0f}s")
        pct = int(current / total * 100) if total > 0 else 0
        self._progress_bar.set_progress(pct)
        self._pct_label.config(text=f"{pct}%")
        self._progress_detail.config(text=f"{current} of {total} files compressed")

    def _reset_stats(self):
        for card in self._stat_cards.values():
            card.set("—")
        self._progress_bar.set_progress(0)
        self._pct_label.config(text="—")
        self._progress_detail.config(text="Waiting…")

    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="Select PDF Files",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
        )
        if paths:
            added = self._file_panel.add_files(list(paths))
            self._log.log(f"{added} PDF file(s) added", "info")
            self._status_cb(f"{added} PDFs added")

    def _add_folder(self):
        folder = filedialog.askdirectory(title="Select Folder with PDF Files")
        if folder:
            paths = glob(os.path.join(folder, "**", "*.pdf"), recursive=True)
            added = self._file_panel.add_files(paths)
            self._log.log(f"Folder scanned — {added} PDF file(s) found", "info")

    def _remove_last(self):
        rows = self._file_panel._rows
        files = self._file_panel._files
        if rows:
            rows[-1].destroy()
            rows.pop()
            files.pop()
            self._file_panel._refresh()

    def _clear_all(self):
        if len(self._file_panel.get_files()) > 0:
            if messagebox.askyesno("Clear All", "Remove all PDFs from the list?"):
                self._file_panel.clear_all()
                self._log.log("File list cleared", "muted")

    def _choose_output(self):
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self._output_var.set(folder)
            self._output_dir = folder
            self._log.log(f"Output: {folder}", "muted")

    def _on_file_count_change(self, count: int):
        self._status_cb(f"{count} PDF(s) in queue")

    def _open_output(self):
        folder = self._output_var.get()
        if not os.path.exists(folder):
            messagebox.showwarning("Error", "Output folder doesn't exist.")
            return
        if platform.system() == "Windows":
            os.startfile(folder)
        elif platform.system() == "Darwin":
            subprocess.run(["open", folder])
        else:
            subprocess.run(["xdg-open", folder])

    def _start_compression(self):
        if self._compressing:
            return
        files = self._file_panel.get_files()
        if not files:
            messagebox.showwarning("Empty Queue", "Add PDF files first.")
            return
        output_dir = self._output_var.get()
        os.makedirs(output_dir, exist_ok=True)
        if self._comp_backend == "unavailable":
            messagebox.showerror(
                "No Compression Engine",
                "No compression engine found.\n\n"
                "Install one of:\n"
                "• Ghostscript (recommended): ghostscript.com\n"
                "• pikepdf: pip install pikepdf\n"
                "• pypdf: pip install pypdf"
            )
            return

        self._compressing = True
        self._reset_stats()
        quality = self._quality_var.get()
        self._log.log("━" * 36, "muted")
        self._log.log(f"Compressing {len(files)} file(s)  [quality: {quality}]", "info")
        self._status_cb("Compressing…")
        self._btn_compress.set_text("◉  Running")

        overwrite = self._overwrite_var.get()
        counter = {"i": 0, "success": 0, "failed": 0, "saved_kb": 0.0}
        t0 = [time.time()]

        def on_start(idx, total, name):
            self._file_panel.mark_converting(idx - 1)
            self._log.log(f"Compressing: {name}", "info")

        def on_done(result: CompressionResult):
            i = counter["i"]
            extra = ""
            if result.success and result.original_size_kb > 0:
                extra = f"-{result.ratio:.0f}%"
                counter["saved_kb"] += result.saved_kb
            self._file_panel.mark_done(i, result.success, result.duration, extra)
            if result.success:
                counter["success"] += 1
                self._log.log(
                    f"✓ {Path(result.source).name}"
                    f"  {result.original_size_kb:.0f}→{result.compressed_size_kb:.0f} KB"
                    f"  (-{result.ratio:.0f}%)"
                    f"  ({result.duration:.1f}s)", "ok"
                )
            else:
                counter["failed"] += 1
                self._log.log(f"✗ {Path(result.source).name}: {result.error}", "err")
            counter["i"] += 1
            elapsed = time.time() - t0[0]
            self._update_stats(counter["success"], counter["failed"],
                               elapsed, counter["i"], len(files), counter["saved_kb"])

        def on_finish(stats: CompressionStats):
            self._compressing = False
            saved_str = (f"{stats.total_saved_kb/1024:.1f} MB"
                         if stats.total_saved_kb >= 1024
                         else f"{stats.total_saved_kb:.0f} KB")
            self._log.log("━" * 36, "muted")
            self._log.log(
                f"Done!  ✓ {stats.success}  ✗ {stats.failed}"
                f"  |  saved {saved_str}  |  {stats.total_time:.1f}s total", "ok"
            )
            self._status_cb(f"Finished: {stats.success}/{stats.total} compressed, saved {saved_str}")
            self._btn_compress.set_text("⚙  Compress")
            if stats.failed > 0:
                self.after(0, lambda: messagebox.showwarning(
                    "Compression Complete",
                    f"✓ Success: {stats.success}\n✗ Failed: {stats.failed}\n\n"
                    "See the activity log for details."
                ))

        def run():
            self._compressor.compress_batch(
                files, output_dir, quality, overwrite,
                on_start=lambda i, t, n: self.after(0, lambda: on_start(i, t, n)),
                on_done=lambda r: self.after(0, lambda: on_done(r)),
                on_finish=lambda s: self.after(0, lambda: on_finish(s)),
            )

        threading.Thread(target=run, daemon=True).start()

    def _cancel_compression(self):
        if self._compressing:
            self._compressor.cancel()
            self._compressing = False
            self._log.log("Compression stopped by user", "warn")
            self._status_cb("Stopped")
            self._btn_compress.set_text("⚙  Compress")


class WordToPDFApp:
    def __init__(self):
        self.root = tk.Tk()
        self._backend = detect_backend()
        self._setup_window()
        self._build_ui()
        self._status_bar_update("Ready", C["text3"])

    def _setup_window(self):
        self.root.title("Word → PDF  Converter & Compressor")
        self.root.geometry("1180x740")
        self.root.minsize(960, 620)
        self.root.configure(bg=C["bg"])
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

    def _build_ui(self):
        self._build_titlebar()
        self._build_tab_bar()
        HSep(self.root).pack(fill="x")
        self._build_content()
        self._build_statusbar()
        # Switch to default tab after everything is fully built
        self.root.after(150, lambda: self._switch_tab("convert"))

    def _build_titlebar(self):
        bar = tk.Frame(self.root, bg=C["bg2"], height=56)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        logo_frame = tk.Frame(bar, bg=C["bg2"])
        logo_frame.pack(side="left", padx=20, pady=8)
        tk.Frame(logo_frame, bg=C["accent"], width=4).pack(side="left", fill="y", padx=(0, 10))
        tk.Label(logo_frame, text="Word → PDF", bg=C["bg2"],
                 fg=C["white"], font=F["title"]).pack(side="left")
        tk.Label(logo_frame, text="  CONVERTER & COMPRESSOR",
                 bg=C["bg2"], fg=C["accent"],
                 font=("Segoe UI", 9, "bold")).pack(side="left", pady=(8, 0))

        right = tk.Frame(bar, bg=C["bg2"])
        right.pack(side="right", padx=20)
        bmap = {
            "libreoffice": ("LibreOffice", C["green"]),
            "win32com":    ("MS Word",     C["accent"]),
            "docx2pdf":    ("docx2pdf",    C["yellow"]),
            "unavailable": ("No Engine",   C["red"]),
        }
        bname, bcolor = bmap.get(self._backend, (self._backend, C["text2"]))
        pill = tk.Frame(right, bg=C["surface2"], padx=12, pady=4)
        pill.pack()
        tk.Label(pill, text="⚙", bg=C["surface2"], fg=bcolor,
                 font=F["body"]).pack(side="left", padx=(0, 5))
        tk.Label(pill, text=bname, bg=C["surface2"], fg=bcolor,
                 font=F["small"]).pack(side="left")

    def _build_tab_bar(self):
        self._tab_bar = tk.Frame(self.root, bg=C["bg2"], height=40)
        self._tab_bar.pack(fill="x")
        self._tab_bar.pack_propagate(False)

        self._active_tab = tk.StringVar(value="convert")
        self._tab_btns = {}

        tabs = [
            ("convert",  "▶  Word → PDF",  C["accent"]),
            ("compress", "⚙  PDF Compress", C["orange"]),
        ]
        for key, label, color in tabs:
            btn = tk.Label(self._tab_bar, text=label,
                           bg=C["bg2"], fg=C["text3"],
                           font=("Segoe UI", 10, "bold"),
                           padx=20, pady=10, cursor="hand2")
            btn.pack(side="left")
            btn.bind("<Button-1>", lambda e, k=key: self._switch_tab(k))
            self._tab_btns[key] = (btn, color)

        self._tab_indicator = tk.Frame(self._tab_bar, height=2, bg=C["accent"])
        self._tab_indicator.place(x=0, y=38, width=0)

    def _switch_tab(self, key: str):
        self._active_tab.set(key)
        for k, (btn, color) in self._tab_btns.items():
            if k == key:
                btn.config(fg=color)
                x = btn.winfo_x()
                w = btn.winfo_width()
                self._tab_indicator.place(x=x, y=38, width=w)
                self._tab_indicator.config(bg=color)
            else:
                btn.config(fg=C["text3"])

        for k, frame in self._tab_frames.items():
            if k == key:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

    def _build_content(self):
        self._content = tk.Frame(self.root, bg=C["bg"])
        self._content.pack(fill="both", expand=True)

        self._tab_frames = {
            "convert":  ConversionTab(self._content, self._status_bar_update),
            "compress": CompressionTab(self._content, self._status_bar_update),
        }

    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=C["surface"], height=26)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self._status_lbl = tk.Label(bar, text="Ready",
                                    bg=C["surface"], fg=C["text3"],
                                    font=F["tiny"], anchor="w")
        self._status_lbl.pack(side="left", padx=14, pady=5)

        comp_backend = detect_compression_backend()
        bname = {
            "libreoffice": "LibreOffice",
            "win32com":    "Microsoft Word",
            "docx2pdf":    "docx2pdf",
            "unavailable": "⚠ No Conv. Engine",
        }.get(self._backend, self._backend)
        cname = {
            "ghostscript": "Ghostscript",
            "pikepdf":     "pikepdf",
            "pypdf":       "pypdf",
            "unavailable": "⚠ No Comp. Engine",
        }.get(comp_backend, comp_backend)

        tk.Label(bar, text=f"Conv: {bname}  |  Comp: {cname}",
                 bg=C["surface"], fg=C["text4"],
                 font=F["tiny"]).pack(side="right", padx=14)

    def _status_bar_update(self, msg: str, color: str = None):
        self._status_lbl.config(text=msg, fg=color or C["text3"])

    def run(self):
        self.root.mainloop()