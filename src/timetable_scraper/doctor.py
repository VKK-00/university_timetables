from __future__ import annotations

import importlib
import subprocess

from .ocr import build_tesseract_env, configure_tesseract


REQUIRED_MODULES = [
    "openpyxl",
    "xlrd",
    "yaml",
    "requests",
    "bs4",
    "pdfplumber",
    "pypdfium2",
    "pytesseract",
]


def run_doctor() -> tuple[bool, list[str]]:
    ok = True
    messages: list[str] = []
    for module_name in REQUIRED_MODULES:
        try:
            importlib.import_module(module_name)
            messages.append(f"OK module {module_name}")
        except Exception as exc:
            ok = False
            messages.append(f"FAIL module {module_name}: {exc.__class__.__name__}")
    tesseract_path = configure_tesseract()
    if not tesseract_path:
        messages.append("FAIL tesseract binary not found in PATH")
        return False, messages
    messages.append(f"OK tesseract {tesseract_path}")
    try:
        result = subprocess.run(
            [tesseract_path, "--list-langs"],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
            env=build_tesseract_env(),
        )
    except Exception as exc:
        return False, [*messages, f"FAIL tesseract probe: {exc.__class__.__name__}"]
    langs = {
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and not line.startswith("List of available")
    }
    missing = {"ukr", "eng"} - langs
    if missing:
        ok = False
        messages.append(f"FAIL tesseract languages missing: {', '.join(sorted(missing))}")
    else:
        messages.append("OK tesseract languages: ukr, eng")
    return ok, messages
