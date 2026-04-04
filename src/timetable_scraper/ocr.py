from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytesseract


WINDOWS_CANDIDATES = [
    Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
    Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
]
LOCAL_TESSDATA_DIR = Path.home() / ".timetable_scraper" / "tessdata"


def find_tesseract_binary() -> str | None:
    found = shutil.which("tesseract")
    if found:
        return found
    for candidate in WINDOWS_CANDIDATES:
        if candidate.exists():
            return str(candidate)
    return None


def configure_tesseract() -> str | None:
    found = find_tesseract_binary()
    if found:
        pytesseract.pytesseract.tesseract_cmd = found
    tessdata_dir = get_tessdata_dir()
    if tessdata_dir:
        os.environ["TESSDATA_PREFIX"] = str(tessdata_dir)
    return found


def get_tessdata_dir() -> Path | None:
    env_prefix = os.environ.get("TESSDATA_PREFIX")
    if env_prefix:
        prefix_path = Path(env_prefix)
        candidate = prefix_path / "tessdata"
        if candidate.exists():
            return candidate
        if prefix_path.exists():
            return prefix_path
    if LOCAL_TESSDATA_DIR.exists():
        return LOCAL_TESSDATA_DIR
    for candidate in WINDOWS_CANDIDATES:
        tessdata = candidate.parent / "tessdata"
        if tessdata.exists():
            return tessdata
    return None


def build_tesseract_env() -> dict[str, str]:
    env = os.environ.copy()
    tessdata_dir = get_tessdata_dir()
    if tessdata_dir:
        env["TESSDATA_PREFIX"] = str(tessdata_dir)
    return env
