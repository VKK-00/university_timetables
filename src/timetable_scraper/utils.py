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
    "i тиждень": "Верхній",
    "1 тиждень": "Верхній",
    "ii тиждень": "Нижній",
    "2 тиждень": "Нижній",
    "ч/т": "Через тиждень",
    "через тиждень": "Через тиждень",
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
    "(?P<start>(?:\\d{1,2}[:.]\\d{2}|\\d{3,4}|\\d(?:\\s+\\d){2,3}))\\s*(?:-|\\u2013|\\u2014)\\s*(?P<end>(?:\\d{1,2}[:.]\\d{2}|\\d{3,4}|\\d(?:\\s+\\d){2,3}))"
)
STORAGE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,}$")
NUMERIC_TOKEN_RE = re.compile(r"^\d+(?:[._-]\d+)*$")
KNOWN_SOURCE_LABELS = {
    "fit.knu.ua": "Факультет інформаційних технологій",
    "phys.knu.ua": "Фізичний факультет",
    "sociology.knu.ua": "Факультет соціології",
    "econom.knu.ua": "Економічний факультет",
    "biomed.knu.ua": "ННЦ Інститут біології та медицини",
    "chem.knu.ua": "Хімічний факультет",
    "history.univ.kiev.ua": "Історичний факультет",
    "history.knu.ua": "Історичний факультет",
    "geo.knu.ua": "Географічний факультет",
    "geol.univ.kiev.ua": "Геологічний факультет",
    "mechmat.knu.ua": "Механіко-математичний факультет",
    "psy.knu.ua": "Факультет психології",
    "law.knu.ua": "Юридичний факультет",
    "rex.knu.ua": "Радіофізичний факультет",
    "iht.knu.ua": "ННІ високих технологій",
    "iir.edu.ua": "Інститут міжнародних відносин",
    "journ.knu.ua": "ННІ журналістики",
    "philology.knu.ua": "ННІ філології",
    "philosophy.knu.ua": "Філософський факультет",
    "mil.knu.ua": "Військовий інститут",
}


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
    text = flatten_multiline(value)
    match = re.search(r"(?<!\d)(\d{1,2})[:.](\d{2})(?![\d.])", text)
    if not match:
        compact = re.fullmatch(r"(\d(?:\s+\d){2,3}|\d{3,4})", text)
        if not compact:
            return ""
        digits = re.sub(r"\s+", "", compact.group(1))
        if len(digits) == 3:
            digits = f"0{digits}"
        hours = int(digits[:-2])
        minutes = int(digits[-2:])
        if hours > 23 or minutes > 59:
            return ""
        return f"{hours:02d}:{minutes:02d}"
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
    if text in DAY_NAMES:
        return DAY_NAMES[text]
    simplified = re.sub(r"\([^)]*\)", " ", text)
    simplified = simplified.replace("'", "").replace("’", "").replace("`", "")
    simplified = re.sub(r"[^a-zа-яіїєґ]+", " ", simplified, flags=re.IGNORECASE)
    normalized = normalize_whitespace(simplified)
    if normalized in DAY_NAMES:
        return DAY_NAMES[normalized]
    collapsed = normalized.replace(" ", "")
    if collapsed in DAY_NAMES:
        return DAY_NAMES[collapsed]
    reversed_collapsed = collapsed[::-1]
    if reversed_collapsed in DAY_NAMES:
        return DAY_NAMES[reversed_collapsed]
    for key, canonical in DAY_NAMES.items():
        if key in normalized or key in collapsed or key in reversed_collapsed:
            return canonical
    return flatten_multiline(value)


def humanize_source_name(value: str) -> str:
    text = normalize_whitespace(value.replace("_", " ").replace("-", " "))
    return text.title() if text else ""


def looks_like_storage_identifier(value: Any) -> bool:
    text = flatten_multiline(value)
    if not text:
        return False
    if text.startswith(("http://", "https://")):
        return True
    if STORAGE_ID_RE.fullmatch(text):
        return True
    if NUMERIC_TOKEN_RE.fullmatch(text):
        return True
    return False


def is_meaningful_label(value: Any) -> bool:
    text = flatten_multiline(value)
    lowered = text.casefold()
    if not text:
        return False
    if lowered in {"невідома програма", "невідомий факультет", "sheet1", "аркуш1", "demo"}:
        return False
    if looks_like_storage_identifier(text):
        return False
    return True


def coalesce_label(*candidates: Any, fallback: str = "") -> str:
    for candidate in candidates:
        text = flatten_multiline(candidate)
        if is_meaningful_label(text):
            return text
    return flatten_multiline(fallback)


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
    parsed = urlparse(locator)
    host = parsed.netloc.casefold().removeprefix("www.")
    if host in KNOWN_SOURCE_LABELS:
        return KNOWN_SOURCE_LABELS[host]
    if "::" in locator:
        _, inner = locator.split("::", 1)
        parts = [part for part in inner.split("/") if part]
        if len(parts) >= 2:
            return parts[1]
    if parsed.scheme and parsed.netloc:
        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) >= 2 and not looks_like_storage_identifier(path_parts[-2]):
            return path_parts[-2]
        return parsed.netloc or "Невідомий факультет"
    parts = [part for part in re.split(r"[\\/]", locator) if part]
    if len(parts) >= 2 and not looks_like_storage_identifier(parts[-2]):
        return parts[-2]
    return host or "Невідомий факультет"


def truncate_sheet_title(value: str) -> str:
    text = flatten_multiline(value) or "Аркуш1"
    return text[:31]
