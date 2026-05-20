import os
import time
import shutil
import subprocess
import platform
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import threading


@dataclass
class ConversionResult:
    source: str
    output: str
    success: bool
    error: Optional[str] = None
    duration: float = 0.0
    file_size_kb: float = 0.0


@dataclass
class ConversionStats:
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    total_time: float = 0.0
    results: list = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.success / self.total) * 100


def detect_backend() -> str:
    """Auto-detect best available conversion backend."""
    lo_paths = [
        "libreoffice", "soffice",
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    for p in lo_paths:
        if shutil.which(p) or os.path.exists(p):
            return "libreoffice"

    if platform.system() == "Windows":
        try:
            import win32com.client
            return "win32com"
        except ImportError:
            pass

    try:
        import docx2pdf 
        return "docx2pdf"
    except ImportError:
        pass

    return "unavailable"


def convert_with_libreoffice(source: str, output_dir: str) -> tuple[bool, str]:
    """Convert using LibreOffice headless mode."""
    lo_bin = "libreoffice"
    for candidate in ["libreoffice", "soffice",
                       r"C:\Program Files\LibreOffice\program\soffice.exe",
                       "/Applications/LibreOffice.app/Contents/MacOS/soffice"]:
        if shutil.which(candidate) or os.path.exists(candidate):
            lo_bin = candidate
            break

    cmd = [
        lo_bin,
        "--headless",
        "--norestore",
        "--convert-to", "pdf",
        "--outdir", output_dir,
        source
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            stem = Path(source).stem
            expected = Path(output_dir) / f"{stem}.pdf"
            return True, str(expected)
        else:
            return False, result.stderr.strip() or "LibreOffice خروجی خطا داد"
    except subprocess.TimeoutExpired:
        return False, "تبدیل بیش از ۱۲۰ ثانیه طول کشید (timeout)"
    except Exception as e:
        return False, str(e)


def convert_with_win32com(source: str, output_path: str) -> tuple[bool, str]:
    """Convert using Microsoft Word COM automation (Windows only)."""
    try:
        import win32com.client
        import pythoncom 
        pythoncom.CoInitialize()
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(os.path.abspath(source))
        doc.SaveAs(os.path.abspath(output_path), FileFormat=17)  # 17 = wdFormatPDF
        doc.Close()
        word.Quit()
        pythoncom.CoUninitialize()
        return True, output_path
    except Exception as e:
        return False, str(e)


def convert_with_docx2pdf(source: str, output_path: str) -> tuple[bool, str]:
    """Convert using docx2pdf library."""
    try:
        from docx2pdf import convert
        convert(source, output_path)
        return True, output_path
    except Exception as e:
        return False, str(e)


class Converter:
    """
    Main converter class. Supports:
    - Batch conversion
    - Per-file callbacks (for progress UI)
    - Cancellation
    - Rename conflict resolution
    - Output file size tracking
    """

    def __init__(self):
        self.backend = detect_backend()
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def reset_cancel(self):
        self._cancel_event.clear()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def get_output_path(self, source: str, output_dir: str, overwrite: bool = False) -> str:
        """Generate output PDF path, handling filename conflicts."""
        stem = Path(source).stem
        base = Path(output_dir) / f"{stem}.pdf"
        if overwrite or not base.exists():
            return str(base)
        counter = 1
        while True:
            candidate = Path(output_dir) / f"{stem}_{counter}.pdf"
            if not candidate.exists():
                return str(candidate)
            counter += 1

    def convert_file(
        self,
        source: str,
        output_dir: str,
        overwrite: bool = False,
    ) -> ConversionResult:
        """Convert a single Word file to PDF."""
        start = time.time()
        output_path = self.get_output_path(source, output_dir, overwrite)

        if self.backend == "libreoffice":
            success, info = convert_with_libreoffice(source, output_dir)
            if success:
                
                lo_output = Path(output_dir) / f"{Path(source).stem}.pdf"
                if str(lo_output) != output_path and lo_output.exists():
                    lo_output.rename(output_path)
        elif self.backend == "win32com":
            success, info = convert_with_win32com(source, output_path)
        elif self.backend == "docx2pdf":
            success, info = convert_with_docx2pdf(source, output_path)
        else:
            success = False
            info = (
                "هیچ موتور تبدیلی یافت نشد.\n"
                "لطفاً LibreOffice یا Microsoft Word نصب کنید."
            )

        duration = time.time() - start
        size_kb = 0.0
        if success and os.path.exists(output_path):
            size_kb = os.path.getsize(output_path) / 1024

        return ConversionResult(
            source=source,
            output=output_path if success else "",
            success=success,
            error=None if success else info,
            duration=duration,
            file_size_kb=size_kb,
        )

    def convert_batch(
        self,
        files: list[str],
        output_dir: str,
        overwrite: bool = False,
        on_start=None,
        on_done=None,
        on_finish=None,
    ) -> ConversionStats:
        """Convert a list of files with progress callbacks."""
        self.reset_cancel()
        stats = ConversionStats(total=len(files))
        t0 = time.time()

        for i, source in enumerate(files):
            if self.is_cancelled():
                stats.skipped += (len(files) - i)
                break

            if on_start:
                on_start(i + 1, len(files), Path(source).name)

            result = self.convert_file(source, output_dir, overwrite)
            stats.results.append(result)

            if result.success:
                stats.success += 1
            else:
                stats.failed += 1

            if on_done:
                on_done(result)

        stats.total_time = time.time() - t0
        if on_finish:
            on_finish(stats)
        return stats
