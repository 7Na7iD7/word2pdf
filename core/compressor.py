import os
import shutil
import subprocess
import time
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable


@dataclass
class CompressionResult:
    source: str
    output: str
    success: bool
    error: Optional[str] = None
    duration: float = 0.0
    original_size_kb: float = 0.0
    compressed_size_kb: float = 0.0

    @property
    def saved_kb(self) -> float:
        return max(0.0, self.original_size_kb - self.compressed_size_kb)

    @property
    def ratio(self) -> float:
        if self.original_size_kb == 0:
            return 0.0
        return (self.saved_kb / self.original_size_kb) * 100


@dataclass
class CompressionStats:
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    total_time: float = 0.0
    total_saved_kb: float = 0.0
    results: list = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.success / self.total) * 100


GHOSTSCRIPT_SETTINGS = {
    "screen":  "/screen",
    "ebook":   "/ebook",
    "printer": "/printer",
    "prepress": "/prepress",
}

QUALITY_LABELS = {
    "screen":  "Screen (72 dpi) — smallest file",
    "ebook":   "eBook (150 dpi) — balanced",
    "printer": "Printer (300 dpi) — high quality",
    "prepress": "Prepress (300 dpi) — max quality",
}


def detect_ghostscript() -> Optional[str]:
    candidates = [
        "gs",
        "gswin64c",
        "gswin32c",
        r"C:\Program Files\gs\gs10.04.0\bin\gswin64c.exe",
        r"C:\Program Files\gs\gs10.03.1\bin\gswin64c.exe",
        r"C:\Program Files\gs\gs10.02.1\bin\gswin64c.exe",
        r"C:\Program Files (x86)\gs\gs10.04.0\bin\gswin32c.exe",
        "/usr/bin/gs",
        "/usr/local/bin/gs",
        "/opt/homebrew/bin/gs",
    ]
    for c in candidates:
        if shutil.which(c) or os.path.exists(c):
            return c
    return None


def detect_pypdf() -> bool:
    try:
        import pypdf
        return True
    except ImportError:
        try:
            import PyPDF2
            return True
        except ImportError:
            return False


def detect_pikepdf() -> bool:
    try:
        import pikepdf
        return True
    except ImportError:
        return False


def detect_compression_backend() -> str:
    if detect_ghostscript():
        return "ghostscript"
    if detect_pikepdf():
        return "pikepdf"
    if detect_pypdf():
        return "pypdf"
    return "unavailable"


def compress_with_ghostscript(
    source: str,
    output: str,
    quality: str = "ebook",
) -> tuple[bool, str]:
    gs = detect_ghostscript()
    if not gs:
        return False, "Ghostscript پیدا نشد"
    setting = GHOSTSCRIPT_SETTINGS.get(quality, "/ebook")
    cmd = [
        gs,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={setting}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        f"-sOutputFile={output}",
        source,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and os.path.exists(output):
            return True, output
        return False, result.stderr.strip() or "Ghostscript خطا داد"
    except subprocess.TimeoutExpired:
        return False, "timeout — بیش از ۱۲۰ ثانیه"
    except Exception as e:
        return False, str(e)


def compress_with_pikepdf(source: str, output: str) -> tuple[bool, str]:
    try:
        import pikepdf
        with pikepdf.open(source) as pdf:
            pdf.save(
                output,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
                normalize_content=True,
            )
        return True, output
    except Exception as e:
        return False, str(e)


def compress_with_pypdf(source: str, output: str) -> tuple[bool, str]:
    try:
        try:
            from pypdf import PdfWriter, PdfReader
        except ImportError:
            from PyPDF2 import PdfWriter, PdfReader

        reader = PdfReader(source)
        writer = PdfWriter()
        for page in reader.pages:
            page.compress_content_streams()
            writer.add_page(page)
        with open(output, "wb") as f:
            writer.write(f)
        return True, output
    except Exception as e:
        return False, str(e)


class Compressor:
    def __init__(self):
        self.backend = detect_compression_backend()
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def reset_cancel(self):
        self._cancel_event.clear()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def get_output_path(self, source: str, output_dir: str, suffix: str = "_compressed", overwrite: bool = False) -> str:
        stem = Path(source).stem
        base = Path(output_dir) / f"{stem}{suffix}.pdf"
        if overwrite or not base.exists():
            return str(base)
        counter = 1
        while True:
            candidate = Path(output_dir) / f"{stem}{suffix}_{counter}.pdf"
            if not candidate.exists():
                return str(candidate)
            counter += 1

    def compress_file(
        self,
        source: str,
        output_dir: str,
        quality: str = "ebook",
        overwrite: bool = False,
    ) -> CompressionResult:
        start = time.time()
        original_size_kb = 0.0
        if os.path.exists(source):
            original_size_kb = os.path.getsize(source) / 1024

        output_path = self.get_output_path(source, output_dir, overwrite=overwrite)

        if self.backend == "ghostscript":
            success, info = compress_with_ghostscript(source, output_path, quality)
        elif self.backend == "pikepdf":
            success, info = compress_with_pikepdf(source, output_path)
        elif self.backend == "pypdf":
            success, info = compress_with_pypdf(source, output_path)
        else:
            success = False
            info = (
                "هیچ موتور فشرده‌سازی یافت نشد.\n"
                "لطفاً Ghostscript، pikepdf یا pypdf نصب کنید."
            )

        duration = time.time() - start
        compressed_size_kb = 0.0
        if success and os.path.exists(output_path):
            compressed_size_kb = os.path.getsize(output_path) / 1024

        return CompressionResult(
            source=source,
            output=output_path if success else "",
            success=success,
            error=None if success else info,
            duration=duration,
            original_size_kb=original_size_kb,
            compressed_size_kb=compressed_size_kb,
        )

    def compress_batch(
        self,
        files: list[str],
        output_dir: str,
        quality: str = "ebook",
        overwrite: bool = False,
        on_start: Optional[Callable] = None,
        on_done: Optional[Callable] = None,
        on_finish: Optional[Callable] = None,
    ) -> CompressionStats:
        self.reset_cancel()
        stats = CompressionStats(total=len(files))
        t0 = time.time()

        for i, source in enumerate(files):
            if self.is_cancelled():
                stats.skipped += (len(files) - i)
                break

            if on_start:
                on_start(i + 1, len(files), Path(source).name)

            result = self.compress_file(source, output_dir, quality, overwrite)
            stats.results.append(result)

            if result.success:
                stats.success += 1
                stats.total_saved_kb += result.saved_kb
            else:
                stats.failed += 1

            if on_done:
                on_done(result)

        stats.total_time = time.time() - t0
        if on_finish:
            on_finish(stats)
        return stats
