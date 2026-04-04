from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


WEEK_TYPES = {
    "обидва": "Обидва",
    "верхній": "Верхній",
    "верхний": "Верхній",
    "нижній": "Нижній",
    "нижний": "Нижній",
}

DAY_NAMES = {
    "понеділок": "Понеділок",
    "вівторок": "Вівторок",
    "второк": "Вівторок",
    "середа": "Середа",
    "четвер": "Четвер",
    "п'ятниця": "П'ятниця",
    "пятниця": "П'ятниця",
    "субота": "Субота",
    "неділя": "Неділя",
}

TIME_RANGE_RE = re.compile(
    r"(?P<start>\d{1,2}[:.]\d{2})\s*[-–—]\s*(?P<end>\d{1,2}[:.]\d{2})"
)


def normalize_whitespace(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", "ignore")
    text = str(value).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text.strip())


def flatten_multiline(value: Any) -> str:
    if value is None:
        return ""
    return normalize_whitespace(str(value).replace("\r", " ").replace("\n", " "))


def normalize_header(value: Any) -> str:
    text = flatten_multiline(value).casefold()
    text = text.replace("(якщо є)", "")
    text = text.replace("’", "'")
    text = re.sub(r"[^0-9a-zа-яіїєґ' ]+", " ", text, flags=re.IGNORECASE)
    return normalize_whitespace(text)


def excel_fraction_to_time(value: float) -> str:
    minutes = round(float(value) * 24 * 60)
    hours, mins = divmod(minutes, 60)
    return f"{hours % 24:02d}:{mins:02d}"


def parse_time_value(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)) and 0 <= float(value) < 1.1:
        return excel_fraction_to_time(float(value))
    match = re.search(r"(\d{1,2})[:.](\d{2})", flatten_multiline(value))
    if not match:
        return ""
    return f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"


def parse_time_range(text: str) -> tuple[str, str]:
    match = TIME_RANGE_RE.search(text or "")
    if not match:
        return "", ""
    return parse_time_value(match.group("start")), parse_time_value(match.group("end"))


def normalize_week_type(value: Any) -> str:
    text = flatten_multiline(value).casefold()
    return WEEK_TYPES.get(text, flatten_multiline(value))


def normalize_day(value: Any) -> str:
    text = flatten_multiline(value).casefold()
    return DAY_NAMES.get(text, flatten_multiline(value))


def slugify_filename(value: str, fallback: str = "untitled") -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[<>:\"/\\\\|?*]+", "_", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text or fallback


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def json_dumps(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def clean_numeric_artifact(value: Any) -> str:
    text = flatten_multiline(value)
    if re.fullmatch(r"\d+\.0", text):
        return text[:-2]
    return text


def excerpt_from_values(values: dict[str, Any], limit: int = 6) -> str:
    parts = [flatten_multiline(v) for v in values.values() if flatten_multiline(v)]
    return " | ".join(parts[:limit])


def infer_faculty_from_locator(locator: str) -> str:
    if "::" in locator:
        _, inner = locator.split("::", 1)
        parts = [part for part in inner.split("/") if part]
        if len(parts) >= 2:
            return parts[1]
    parts = [part for part in re.split(r"[\\/]", locator) if part]
    if len(parts) >= 2:
        return parts[-2]
    host = urlparse(locator).netloc
    return host or "Невідомий факультет"


def truncate_sheet_title(value: str) -> str:
    text = flatten_multiline(value) or "Аркуш1"
    return text[:31]
