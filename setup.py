import sys
import os
import subprocess
import shutil
from pathlib import Path

BASE = Path(__file__).parent
VENV = BASE / "venv"

BANNER = """
╔══════════════════════════════════════════════════╗
║       Batch Word → PDF Converter  v2.0           ║
║              Setup & Install                     ║
╚══════════════════════════════════════════════════╝
"""

def run(cmd, **kw):
    return subprocess.run(cmd, **kw)

def check_python():
    v = sys.version_info
    if v < (3, 9):
        print(f"❌ Python 3.9+ لازم است. نسخه فعلی: {v.major}.{v.minor}")
        sys.exit(1)
    print(f"✅ Python {v.major}.{v.minor}.{v.micro}")

def create_venv():
    if VENV.exists():
        print("✅ محیط مجازی موجود است")
        return
    print("⏳ ساخت محیط مجازی (venv)…")
    run([sys.executable, "-m", "venv", str(VENV)], check=True)
    print("✅ محیط مجازی ساخته شد")

def pip_install(packages):
    pip = VENV / ("Scripts/pip.exe" if os.name == "nt" else "bin/pip")
    print(f"⏳ نصب پکیج‌ها: {', '.join(packages)}")
    run([str(pip), "install", "--upgrade", *packages], check=True)
    print("✅ پکیج‌ها نصب شدند")

def check_libreoffice():
    for candidate in ["libreoffice", "soffice",
                       r"C:\Program Files\LibreOffice\program\soffice.exe"]:
        if shutil.which(candidate) or os.path.exists(candidate):
            print(f"✅ LibreOffice یافت شد: {candidate}")
            return True
    print("⚠  LibreOffice نصب نشده — از https://libreoffice.org دانلود کنید")
    print("   (بدون آن تبدیل روی Linux/Mac امکان‌پذیر نیست)")
    return False

def write_launcher():
    """Write platform-specific run script."""
    if os.name == "nt":
        launcher = BASE / "run.bat"
        launcher.write_text(
            f'@echo off\n"{VENV / "Scripts/python.exe"}" "{BASE / "main.py"}"\npause\n'
        )
        print(f"✅ لانچر ساخته شد: {launcher}")
    else:
        launcher = BASE / "run.sh"
        launcher.write_text(
            f'#!/bin/bash\n"{VENV / "bin/python"}" "{BASE / "main.py"}"\n'
        )
        launcher.chmod(0o755)
        print(f"✅ لانچر ساخته شد: {launcher}")

def main():
    print(BANNER)
    check_python()
    create_venv()
    pip_install(["docx2pdf", "pywin32"] if os.name == "nt" else ["docx2pdf"])
    check_libreoffice()
    write_launcher()
    print("\n✨ نصب کامل شد!")
    if os.name == "nt":
        print("   اجرا: run.bat")
    else:
        print("   اجرا: ./run.sh  یا  python main.py")

if __name__ == "__main__":
    main()
