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

WEEK_TYPE_PATTERNS = (
    (re.compile(r"(?iu)\b(?:верх(?:ній|нiй)|по\s+верхньому|верхнім?\s+тиж)"), "Верхній"),
    (re.compile(r"(?iu)\b(?:ниж(?:ній|нiй)|по\s+нижньому|нижнім?\s+тиж)"), "Нижній"),
    (re.compile(r"(?iu)\b(?:i|1)\s*тиж"), "Верхній"),
    (re.compile(r"(?iu)\b(?:ii|2)\s*тиж"), "Нижній"),
    (re.compile(r"(?iu)\bнепар"), "Верхній"),
    (re.compile(r"(?iu)\bпарн"), "Нижній"),
    (re.compile(r"(?iu)\bч/т\b"), "Через тиждень"),
    (re.compile(r"(?iu)\bчерез\s+тиждень\b"), "Через тиждень"),
)

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
LINK_TEXT_RE = re.compile(r"(?iu)(https?://\S+|(?:zoom|teams|meet)(?:[\w./:@?=#&%-]+)?)")
ROOM_TEXT_RE = re.compile(
    r"(?iu)\b(?:ауд\.?\s*[\w./-]+|аудитор(?:ія|iя)\s*[\w./-]+|каб\.?\s*[\w./-]+|корп(?:ус|\.)?\s*[\w./-]+|online|онлайн)\b"
)
TEACHER_TEXT_RE = re.compile(
    r"(?iu)(?:\b(?:проф|доц|ас|викл|ст\.?\s*викл|phd|к\.\s*[юф]\.\s*н|д\.\s*[юф]\.\s*н)\.?\b|[А-ЯІЇЄҐ][а-яіїєґ'-]+\s*[А-ЯІЇЄҐ]\.\s*[А-ЯІЇЄҐ]\.)"
)
SERVICE_TEXT_PATTERNS = (
    re.compile(r"(?iu)\bрозклад\s+занять\b"),
    re.compile(r"(?iu)\bграфік\b"),
    re.compile(r"(?iu)\bсписки\s+груп\b"),
    re.compile(r"(?iu)\bтеоретичне\s+навчання\b"),
    re.compile(r"(?iu)\bдень\s+самостійної\s+роботи\b"),
    re.compile(r"(?iu)\bкурс\s+за\s+вибором\b"),
    re.compile(r"(?iu)\bдисциплін\w*\s+вільного\s+вибору\b"),
    re.compile(r"(?iu)\bіноземна\s+мова\s*:\s*нормативний\s+курс\b"),
    re.compile(r"(?iu)\bінформаційний\s+проспект\b"),
    re.compile(r"(?iu)\bправила\s+прийому\b"),
    re.compile(r"(?iu)\bнаукові\s+керівники\b"),
    re.compile(r"(?iu)\bпрограма\s+розвитку\b"),
    re.compile(r"(?iu)\bзвіт\s+декана\b"),
    re.compile(r"(?iu)\bmeeting\s+id\b"),
    re.compile(r"(?iu)\bpasscode\b"),
    re.compile(r"(?iu)\bкод\s+доступу\b"),
    re.compile(r"(?iu)\bідентифікатор\s+конференції\b"),
    re.compile(r"(?iu)\bидентификатор\s+конференции\b"),
    re.compile(r"(?iu)\b(?:в\.?\s*о\.?\s*)?декан(?:а)?\s+факультету\b"),
    re.compile(r"(?iu)\bдиректор(?:а)?\s+інституту\b"),
    re.compile(r"(?iu)\bпроректор(?:а)?\b"),
    re.compile(r"(?iu)\bректор(?:а)?\b"),
    re.compile(r"(?iu)\bтаблиця\s+\d+\b"),
    re.compile(r"(?iu)\bрозгляд\s+та\s+затвердження\b"),
    re.compile(r"(?iu)\bнавчально-методичн"),
    re.compile(r"(?iu)\bстудентів\s+по\s+кафедрах\b"),
    re.compile(r"(?iu)\bнавчальний\s+рік\s+за\s+спеціальністю\b"),
)
COMPACT_SERVICE_MARKERS = (
    "деньсамостійноїроботи",
    "деньсамостiйноїроботи",
    "курсзавибором",
    "дисциплінивільноговиборустудента",
    "дисциплінивільноговибору",
    "вибірковадисципліна",
    "вибірковідисципліни",
    "іноземнамованормативнийкурс",
)
TECHNICAL_LABEL_PATTERNS = (
    re.compile(r"(?iu)^pdf(?:-table.*)?$"),
    re.compile(r"(?iu)^table-\d+$"),
    re.compile(r"(?iu)^page$"),
    re.compile(r"(?iu)^sheet\d+$"),
    re.compile(r"(?iu)^лист\d+$"),
    re.compile(r"(?iu)^аркуш\d+$"),
    re.compile(r"(?iu)^переглянути$"),
    re.compile(r"(?iu)^view(?:[?=_-].+)?$"),
    re.compile(r"(?iu)^edit(?:[?=_-].+)?$"),
    re.compile(r"(?iu)^gid[_=-]?\d+$"),
    re.compile(r"(?iu)^\w+\?usp=.*$"),
)
URLISH_TEXT_PATTERNS = (
    re.compile(r"(?iu)\bhttps?\s*:\s*/\s*/"),
    re.compile(r"(?iu)\bwww\.\S+"),
    re.compile(r"(?iu)\b(?:docs|drive)\.google\.com\b"),
    re.compile(r"(?iu)\bwp-content\b"),
    re.compile(r"(?iu)\b(?:onedrive|1drv)\b"),
)
ADMIN_TEXT_PATTERNS = (
    re.compile(r"(?iu)\b(?:в\.?\s*о\.?\s*)?декан(?:а)?\b"),
    re.compile(r"(?iu)\bдиректор(?:а)?\b"),
    re.compile(r"(?iu)\bпроректор(?:а)?\b"),
    re.compile(r"(?iu)\bректор(?:а)?\b"),
    re.compile(r"(?iu)\bзав(?:\.\s*|ідувач)"),
)
ROOMISH_SUBJECT_PATTERNS = (
    re.compile(r"(?iu)^(?:л|л\.|лек|лекція|пр|пр\.|практ|лаб|лаб\.|сем|сем\.)$"),
    re.compile(r"(?iu)^(?:кяф\s*)?\d{2,4}(?:,\d{2,4})?(?:\s*(?:л|л\.|лек|лекція|пр|пр\.|практ|лаб|лаб\.|сем|сем\.))?$"),
    re.compile(r"(?iu)^(?:л|л\.|лек|лекція|пр|пр\.|практ|лаб|лаб\.|сем|сем\.)[, ]\s*\d{2,4}$"),
    re.compile(r"(?iu)^лаб\.?\s*(?:кяф\s*)?\d{2,4}$"),
    re.compile(r"(?iu)^\d{2,4}\s*/\s*(?:л|л\.|лек|лекція|пр|пр\.|практ|лаб|лаб\.|сем|сем\.)$"),
    re.compile(r"(?iu)^(?:кяф|каф)\s*\d{2,4}$"),
    re.compile(r"(?iu)^\d{2,4}\s*ауд\.?$"),
    re.compile(r"(?iu)^ауд\.?\s*\d{2,4}$"),
)
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


def normalize_week_type_meta(value: Any, *contexts: Any) -> tuple[str, str]:
    explicit = normalize_week_type(value)
    if explicit:
        return explicit, "explicit"
    for context in contexts:
        text = flatten_multiline(context)
        if not text:
            continue
        for pattern, canonical in WEEK_TYPE_PATTERNS:
            if pattern.search(text):
                return canonical, "inferred"
    return "Обидва", "default"


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


def looks_like_technical_label(value: Any) -> bool:
    text = flatten_multiline(value)
    if not text:
        return False
    return any(pattern.search(text) for pattern in TECHNICAL_LABEL_PATTERNS)


def looks_like_urlish_text(value: Any) -> bool:
    text = flatten_multiline(value)
    if not text:
        return False
    return any(pattern.search(text) for pattern in URLISH_TEXT_PATTERNS)


def looks_like_admin_text(value: Any) -> bool:
    text = flatten_multiline(value)
    if not text:
        return False
    return any(pattern.search(text) for pattern in ADMIN_TEXT_PATTERNS)


def looks_like_roomish_subject_text(value: Any) -> bool:
    text = normalize_service_tokens(value)
    if not text:
        return False
    return any(pattern.fullmatch(text) for pattern in ROOMISH_SUBJECT_PATTERNS)


def is_meaningful_label(value: Any) -> bool:
    text = flatten_multiline(value)
    lowered = text.casefold()
    if not text:
        return False
    if lowered in {"невідома програма", "невідомий факультет", "sheet1", "аркуш1", "demo"}:
        return False
    if looks_like_storage_identifier(text):
        return False
    if looks_like_urlish_text(text):
        return False
    if looks_like_technical_label(text):
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


def normalize_service_tokens(value: Any) -> str:
    text = flatten_multiline(value)
    if not text:
        return ""
    text = text.replace("ауд ", "ауд. ").replace("АУД ", "ауд. ")
    text = re.sub(r"(?iu)\bлек\b", "лек.", text)
    text = re.sub(r"(?iu)\bпракт\b", "практ.", text)
    text = re.sub(r"(?iu)\b(лек|практ|сем|лаб|lek|prac|sem|lab)\.{2,}", r"\1.", text)
    text = re.sub(r"\s*([|/;])\s*", r" \1 ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,;")
    return text


def contains_link_text(value: Any) -> bool:
    return bool(LINK_TEXT_RE.search(flatten_multiline(value)))


def looks_like_room_text(value: Any) -> bool:
    return bool(ROOM_TEXT_RE.search(flatten_multiline(value)))


def looks_like_teacher_text(value: Any) -> bool:
    return bool(TEACHER_TEXT_RE.search(flatten_multiline(value)))


def looks_like_service_text(value: Any) -> bool:
    text = flatten_multiline(value)
    if not text:
        return False
    lowered = text.casefold()
    if any(pattern.search(lowered) for pattern in SERVICE_TEXT_PATTERNS):
        return True
    compact = re.sub(r"[\W_]+", "", lowered, flags=re.UNICODE)
    return bool(compact) and any(marker in compact for marker in COMPACT_SERVICE_MARKERS)


def looks_like_garbage_text(value: Any) -> bool:
    text = flatten_multiline(value)
    if not text:
        return False
    tokens = text.split()
    if len(text) > 220:
        return True
    if tokens:
        short_ratio = sum(1 for token in tokens if len(re.sub(r"[^\w]", "", token, flags=re.UNICODE)) <= 1) / len(tokens)
        if len(tokens) >= 8 and short_ratio >= 0.45:
            return True
    symbol_ratio = sum(1 for character in text if character in "/|[]{}_=+") / max(len(text), 1)
    if len(text) >= 80 and symbol_ratio >= 0.18:
        return True
    compact = re.sub(r"[\W_]+", "", text, flags=re.UNICODE)
    if compact and len(compact) >= 60 and len(set(compact.casefold())) <= 8:
        return True
    compact_token = text.replace(" ", "")
    if " " not in text and re.fullmatch(r"[A-Za-z0-9+/=_-]{8,}", compact_token):
        has_signal = (
            any(character.isdigit() for character in compact_token)
            or any(character in "+/=_-" for character in compact_token)
            or (re.search(r"[A-Z]", compact_token) and re.search(r"[a-z]", compact_token))
        )
        if has_signal:
            return True
    return False


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


def infer_asset_label_from_locator(locator: str) -> str:
    parsed = urlparse(locator)
    candidates: list[str] = []
    if parsed.scheme and parsed.netloc:
        path_parts = [part for part in parsed.path.split("/") if part]
        for part in reversed(path_parts):
            lowered = part.casefold()
            if lowered in {"view", "edit", "pubhtml", "export", "download", "file", "d"}:
                continue
            if looks_like_storage_identifier(part):
                continue
            candidates.append(Path(part).stem)
    else:
        stem = Path(locator).stem
        if not looks_like_storage_identifier(stem):
            candidates.append(stem)

    for candidate in candidates:
        text = candidate.replace("_", " ").replace("-", " ")
        text = re.sub(r"(?<=[A-Za-z])(?=[А-ЯІЇЄҐа-яіїєґ])", " ", text)
        text = re.sub(r"(?<=[А-ЯІЇЄҐа-яіїєґ])(?=[A-Za-z])", " ", text)
        text = normalize_whitespace(text)
        if looks_like_storage_identifier(text.replace(" ", "")):
            continue
        if is_meaningful_label(text):
            return text
    return ""


def truncate_sheet_title(value: str) -> str:
    text = flatten_multiline(value) or "Аркуш1"
    text = re.sub(r"[:\\/?*\[\]]+", " ", text)
    text = normalize_whitespace(text)
    return text[:31]
