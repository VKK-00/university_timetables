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
DATE_OR_TIME_LABEL_RE = re.compile(r"(?iu)^\d{2}\.\d{2}\.\d{4}(?:\s+\d{1,2}[:._]\d{2})?$")
MEETING_CODE_RE = re.compile(r"(?iu)^[a-z]{3}-[a-z]{4}-[a-z]{3,4}$")
OPAQUE_CODE_LABEL_RE = re.compile(r"^[A-Za-z0-9]{6,}(?:\.\d+)?$")
LATIN_TEACHER_LABEL_RE = re.compile(
    r"(?u)^(?:(?:dr|prof|professor|associate professor|assistant|lecturer)\.?\s+)?"
    r"[A-Z][A-Za-z'’ʼ-]+(?:\s+[A-Z][A-Za-z'’ʼ-]+){1,3}$"
)
COMPACT_TEACHER_LABEL_RE = re.compile(r"(?u)^[А-ЯІЇЄҐ][а-яіїєґ'’ʼ-]+\s+[А-ЯІЇЄҐ]\.\s*[А-ЯІЇЄҐ]\.?$")
LINK_TEXT_RE = re.compile(r"(?iu)(https?://\S+|(?:zoom|teams|meet)(?:[\w./:@?=#&%-]+)?)")
ROOM_TEXT_RE = re.compile(
    r"(?iu)\b(?:ауд\.?\s*[\w./-]+|аудитор(?:ія|iя)\s*[\w./-]+|каб\.?\s*[\w./-]+|корпус\s*[\dA-Za-zА-ЯІЇЄҐ./-]+|корп\.\s*[\dA-Za-zА-ЯІЇЄҐ./-]+|корп\s+\d[\dA-Za-zА-ЯІЇЄҐ./-]*|online|онлайн)\b"
)
TEACHER_TEXT_RE = re.compile(
    r"(?iu)(?:\b(?:проф|доц|ас|викл|ст\.?\s*викл|phd|к\.\s*[юф]\.\s*н|д\.\s*[юф]\.\s*н)\.?\b|[А-ЯІЇЄҐ][а-яіїєґ'’ʼ-]+\s*[А-ЯІЇЄҐ]\.\s*[А-ЯІЇЄҐ]\.)"
)
SERVICE_TEXT_PATTERNS = (
    re.compile(r"(?iu)\bрозклад\s+занять\b"),
    re.compile(r"(?iu)\bграфік\b"),
    re.compile(r"(?iu)\bсписки\s+груп\b"),
    re.compile(r"(?iu)\bтеоретичне\s+навчання\b"),
    re.compile(r"(?iu)\bдень\s+самостійної\s+роботи\b"),
    re.compile(r"(?iu)\bвільний\s+день\b"),
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
    re.compile(r"(?iu)\bзустріч\s+щодо\b"),
    re.compile(r"(?iu)\bпочаток\s+о\s+\d{1,2}[:.]\d{2}\b"),
    re.compile(r"(?iu)\bурочисте\s+вручення\s+заліковок\b"),
)
COMPACT_SERVICE_MARKERS = (
    "деньсамостійноїроботи",
    "деньсамостiйноїроботи",
    "вільнийдень",
    "вiльнийдень",
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
    re.compile(r"(?iu)^uploads$"),
    re.compile(r"(?iu)^wp[-_\s]*content$"),
    re.compile(r"(?iu)^spreadsheets?$"),
    re.compile(r"(?iu)^files?$"),
    re.compile(r"(?iu)^upload$"),
)
BAD_PROGRAM_LABEL_PATTERNS = (
    re.compile(r"(?iu)^розклад\b.*$"),
    re.compile(r"(?iu)^rozklad\b.*$"),
    re.compile(r"(?iu)^schedule(?:\s+of\s+classes)?$"),
    re.compile(r"(?iu)^schedule\s+of\s+classes\b.*$"),
    re.compile(r"(?iu)^timetable\b.*$"),
    re.compile(r"(?iu)^uploads$"),
    re.compile(r"(?iu)^upload$"),
    re.compile(r"(?iu)^wp[-_\s]*content$"),
    re.compile(r"(?iu)^spreadsheets?$"),
    re.compile(r"(?iu)^files?$"),
    re.compile(r"(?iu)^schedule$"),
    re.compile(r"(?iu)^«?\s*затверджую\s*»?$"),
    re.compile(r"(?iu)^розклад(?:\s+занять)?$"),
    re.compile(r"(?iu)^(?:денна|заочна)\s+форма\s+навчання$"),
    re.compile(r"(?iu)^\d+\s*пара\b.*(?:\d{1,2}[:.]\d{2})"),
    re.compile(r"(?iu)^(?:[ivx]+|\d+)\s+група$"),
    re.compile(r"(?iu)^[12]\s*підгр\.?$"),
    re.compile(r"(?iu)^\d+\s*курс\b.*$"),
    re.compile(r"(?iu)^\d+\s*магістр\w*.*$"),
    re.compile(r"(?iu)^\d+\s*бакалавр\w*.*$"),
    re.compile(r"(?iu)^\d{4}\s+\d{4}\s+\d+\s*sem\b.*$"),
    re.compile(r"(?iu)^\d+\s*sem\.\b.*$"),
    re.compile(r"(?iu)^(?:\d+\s+){1,3}[A-Za-z0-9+/=_-]{6,}$"),
    re.compile(r"(?iu)^начитка!?$"),
    re.compile(r"(?iu)^настановча(?:\s+сесія)?(?:\s+\d.*)?$"),
    re.compile(r"(?iu)^постійний(?:\s+розклад)?!?$"),
    re.compile(r"(?iu)^постійне!?$"),
    re.compile(r"(?iu)^списки?\s+груп$"),
    re.compile(r"(?iu)^початок\s+занять.*$"),
    re.compile(r"(?iu)^навчання\s+з\s+використанням.*$"),
    re.compile(r"(?iu)^увага[!.\s].*$"),
    re.compile(r"(?iu)^[а-яіїєґ'’ʼ-]+\s+факультету$"),
    re.compile(r"(?iu)^інституту\s+журналістики.*$"),
    re.compile(r"(?iu)^dr\.?\s+[A-ZА-ЯІЇЄҐ].*$"),
    re.compile(r"(?iu)^(?:асп|доц|проф|асист|викл)\.?\s*[A-ZА-ЯІЇЄҐ].*$"),
    re.compile(r"(?iu)^[ivxlcdm]+\s*потік\b.*$"),
    re.compile(r"(?iu)^практ\.?\s+.*$"),
    re.compile(r"(?iu)^чл\.-?кор\.?\s+.*$"),
    re.compile(r"(?iu)^english$"),
    re.compile(r"(?iu)^англ\.?\s*мова$"),
    re.compile(r"(?iu)^[лпс]-\d+\s*год\.?$"),
)
BAD_PROGRAM_COMPACT_MARKERS = {
    "розклад",
    "розкладзанять",
    "rozklad",
    "деннаформанавчання",
    "заочнаформанавчання",
    "затверджую",
    "wpcontent",
    "spreadsheets",
    "spreadsheet",
    "upload",
    "uploads",
    "files",
    "file",
    "спискигруп",
    "начитка",
    "постійний",
    "постійне",
}
PROGRAM_CANDIDATE_ALIASES = {
    "генетичнии аналіз": "Генетичний аналіз",
    "доклінічнии аналіз продуктів біотехнологіі": "Доклінічний аналіз продуктів біотехнології",
}
PROGRAM_CODE_RE = re.compile(r"(?iu)\b(?:E\d{1,3}|0\d{2}|1\d{2})\b")
SPACED_WEEKDAY_LABELS = {
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "понеділок",
    "вівторок",
    "середа",
    "четвер",
    "пятниця",
    "п'ятниця",
    "субота",
    "неділя",
}
FORBIDDEN_SUBJECT_PATTERNS = (
    re.compile(r"(?iu)^дист\.?$"),
    re.compile(r"(?iu)^дистанц\.?$"),
    re.compile(r"(?iu)^дистанційно$"),
    re.compile(r"(?iu)^асист\.?$"),
    re.compile(r"(?iu)^\((?:пр|л|лаб|сем)\)\s*\d*$"),
    re.compile(r"(?iu)^[12]\s*підгр\.?$"),
    re.compile(r"(?iu)^комісія$"),
    re.compile(r"(?iu)^блок$"),
    re.compile(r"(?iu)^на\s+\d{1,2}[:.]\d{2}$"),
    re.compile(r"(?iu)^(?:іспит|залік|захист|екзамен)$"),
    re.compile(r"(?iu)^самостійна\s+робота$"),
    re.compile(r"(?iu)^самост[іi]й[-\s/]*н\w*(?:\s*/\s*|\s+)робот\w*$"),
    re.compile(r"(?iu)^день\s+самост[іi]йної\s+роботи$"),
    re.compile(r"(?iu)^вільний\s+день$"),
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
    re.compile(r"(?iu)^(?:л|л\.|лек|лекція|пр|пр\.|практ|лаб|лаб\.|сем|сем\.)\s*/\s*(?:л|л\.|лек|лекція|пр|пр\.|практ|лаб|лаб\.|сем|сем\.)$"),
    re.compile(r"(?iu)^(?:л|л\.|лек|лекція|пр|пр\.|практ|лаб|лаб\.|сем|сем\.)\s*(?:кяф|каф)\s*\d{2,4}$"),
    re.compile(r"(?iu)^\d{2,4}\s*,\s*(?:л|л\.|лек|лекція|пр|пр\.|практ|лаб|лаб\.|сем|сем\.)$"),
    re.compile(r"(?iu)^(?:кяф|каф)\s*,\s*(?:л|л\.|лек|лекція|пр|пр\.|практ|лаб|лаб\.|сем|сем\.)$"),
)
ROOM_LABEL_FRAGMENT_RE = re.compile(r"(?iu)^(?:ауд|каб|корп)\.?$|^(?:\d{2,4}[а-яіїєґa-z]?|[а-яіїєґa-z]-?\d{2,4})$")
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
    if DATE_OR_TIME_LABEL_RE.fullmatch(text):
        return True
    if MEETING_CODE_RE.fullmatch(text):
        return True
    if " " not in text and "?" in text and "=" in text:
        return True
    if " " not in text and "=" in text and "&" in text and re.search(r"[A-Za-z]", text):
        return True
    if re.search(r"(?iu)\b(?:passcode|pwd=|ідентифікатор\s+конференц\w*|код\s+доступ\w*)\b", text):
        return True
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


def looks_like_bad_program_label(value: Any) -> bool:
    text = normalize_service_tokens(value)
    if not text:
        return False
    normalized_candidate = normalize_program_candidate(text)
    if text and not normalized_candidate:
        return True
    stripped = normalized_candidate.lstrip(" .,:;-")
    compact = re.sub(r"[\W_]+", "", text.casefold(), flags=re.UNICODE)
    if " " not in text and len(text) >= 8 and any(character.isdigit() for character in text) and any(character.isalpha() for character in text):
        return True
    if " " not in text and looks_like_storage_identifier(text):
        return True
    if looks_like_urlish_text(text):
        return True
    if looks_like_technical_label(text):
        return True
    if looks_like_admin_text(text):
        return True
    if len(text) >= 20 and any(
        marker in text.casefold()
        for marker in ("розклад", "начитк", "постійн", "тимчасов", "увага", "навчання з використанням")
    ):
        return True
    if _looks_like_month_only_program_label(text) or _looks_like_date_week_program_label(text):
        return True
    if count_program_codes(text) >= 2:
        return True
    if re.search(r"(?u)\b\d{3}\s+\d{3}\s+\d{4}\b", text):
        return True
    if _has_dangling_conjunction_segment(text):
        return True
    if _has_lowercase_followup_segment(text):
        return True
    if _looks_like_group_aggregate_program_label(text):
        return True
    if re.search(r"(?iu)\b(?:ауд|корп)\.?\b", text):
        return True
    if looks_like_teacher_text(stripped) or _looks_like_latin_teacher_label(stripped) or _looks_like_compact_teacher_label(stripped):
        return True
    if looks_like_forbidden_subject_text(stripped):
        return True
    if _looks_like_non_program_segment_combo(text):
        return True
    if re.fullmatch(r"(?iu)(?:[ivxlcdmі]+|\d+)\s+група", text):
        return True
    if _looks_like_opaque_code_label(text):
        return True
    if _looks_like_technical_program_segments(text):
        return True
    if looks_like_garbage_text(text):
        has_digits = any(character.isdigit() for character in text)
        has_code_symbols = any(character in "+/=_-;:" for character in text)
        has_many_latin_caps = bool(re.search(r"[A-Z].*[A-Z]", text)) and bool(re.search(r"[a-z]", text))
        if (has_digits or has_code_symbols or has_many_latin_caps) and not _looks_like_cohort_label(text):
            return True
    if _looks_like_room_label_fragment(stripped):
        return True
    if looks_like_room_text(text) or looks_like_roomish_subject_text(text):
        return True
    if any(pattern.fullmatch(text) for pattern in BAD_PROGRAM_LABEL_PATTERNS):
        return True
    if compact in BAD_PROGRAM_COMPACT_MARKERS:
        return True
    return compact.startswith("розклад") and len(text) <= 24


def coalesce_program_label(*candidates: Any, fallback: str = "") -> str:
    for candidate in candidates:
        text = normalize_program_candidate(candidate)
        if not text:
            continue
        if looks_like_bad_program_label(text):
            continue
        if is_meaningful_label(text):
            return text
    fallback_text = normalize_program_candidate(fallback)
    if fallback_text and not looks_like_bad_program_label(fallback_text) and is_meaningful_label(fallback_text):
        return fallback_text
    return ""


def normalize_program_candidate(value: Any) -> str:
    text = normalize_service_tokens(value).strip(" .,:;-")
    if not text:
        return ""
    segments = [
        normalize_service_tokens(segment).strip(" .,:;-")
        for segment in re.split(r"\s*;\s*", text)
        if normalize_service_tokens(segment).strip(" .,:;-")
    ]
    if not segments:
        return ""
    if len(segments) == 1:
        stripped = segments[0].lstrip(". ").strip()
        if not stripped:
            return ""
        if DATE_OR_TIME_LABEL_RE.fullmatch(stripped):
            return ""
        if stripped.casefold() in {".com", "com"}:
            return ""
        if looks_like_room_text(stripped) or looks_like_roomish_subject_text(stripped) or _looks_like_room_label_fragment(stripped):
            return ""
        if looks_like_forbidden_subject_text(stripped):
            return ""
        if looks_like_teacher_text(stripped) or _looks_like_latin_teacher_label(stripped) or _looks_like_compact_teacher_label(stripped):
            return ""
        if looks_like_technical_label(stripped) or looks_like_urlish_text(stripped):
            return ""
        return PROGRAM_CANDIDATE_ALIASES.get(stripped.casefold(), stripped)

    cleaned_segments: list[str] = []
    for segment in segments:
        stripped = segment.lstrip(". ").strip(" ,")
        if not stripped:
            continue
        if DATE_OR_TIME_LABEL_RE.fullmatch(stripped):
            continue
        if stripped.casefold() in {".com", "com"}:
            continue
        if looks_like_room_text(stripped) or looks_like_roomish_subject_text(stripped) or _looks_like_room_label_fragment(stripped):
            continue
        if looks_like_forbidden_subject_text(stripped):
            continue
        if looks_like_teacher_text(stripped) or _looks_like_latin_teacher_label(stripped) or _looks_like_compact_teacher_label(stripped):
            continue
        if looks_like_technical_label(stripped) or looks_like_urlish_text(stripped):
            continue
        cleaned_segments.append(stripped)

    if not cleaned_segments:
        return ""
    if len(cleaned_segments) == 1:
        return PROGRAM_CANDIDATE_ALIASES.get(cleaned_segments[0].casefold(), cleaned_segments[0])
    combined = " ; ".join(normalize_whitespace(segment) for segment in cleaned_segments)
    return PROGRAM_CANDIDATE_ALIASES.get(combined.casefold(), combined)


def _looks_like_opaque_code_label(text: str) -> bool:
    if not OPAQUE_CODE_LABEL_RE.fullmatch(text):
        return False
    has_digits = any(character.isdigit() for character in text)
    has_upper = any(character.isupper() for character in text)
    has_lower = any(character.islower() for character in text)
    return has_digits and has_upper and has_lower


def _looks_like_technical_program_segments(text: str) -> bool:
    segments = [segment.strip(" .") for segment in re.split(r"\s*;\s*", text) if segment.strip(" .")]
    if len(segments) < 2:
        return False
    technical_segments = sum(1 for segment in segments if _is_technical_program_segment(segment))
    if technical_segments == 0:
        return False
    meaningful_segments = sum(1 for segment in segments if _is_meaningful_program_segment(segment))
    return meaningful_segments == 0 or technical_segments >= len(segments) - 1


def _is_technical_program_segment(segment: str) -> bool:
    cleaned = normalize_service_tokens(segment).strip(" .")
    if not cleaned:
        return False
    if DATE_OR_TIME_LABEL_RE.fullmatch(cleaned):
        return True
    if MEETING_CODE_RE.fullmatch(cleaned):
        return True
    if _looks_like_opaque_code_label(cleaned):
        return True
    if cleaned.casefold() in {".com", "com"}:
        return True
    if looks_like_room_text(cleaned):
        return True
    if looks_like_urlish_text(cleaned):
        return True
    if looks_like_technical_label(cleaned):
        return True
    return False


def _is_meaningful_program_segment(segment: str) -> bool:
    cleaned = normalize_service_tokens(segment)
    if not cleaned:
        return False
    if _is_technical_program_segment(cleaned):
        return False
    words = re.findall(r"(?iu)[A-Za-zА-ЯІЇЄҐа-яіїєґ'’ʼ-]{3,}", cleaned)
    return bool(words) and sum(len(word) for word in words) >= 6 and not looks_like_admin_text(cleaned)


def _looks_like_non_program_segment_combo(text: str) -> bool:
    segments = [normalize_service_tokens(segment).strip(" .,:;-") for segment in re.split(r"\s*;\s*", text) if normalize_service_tokens(segment).strip(" .,:;-")]
    if len(segments) < 2:
        return False
    return all(
        (
            DATE_OR_TIME_LABEL_RE.fullmatch(segment)
            or segment.casefold() in {".com", "com"}
            or looks_like_room_text(segment)
            or looks_like_roomish_subject_text(segment)
            or _looks_like_room_label_fragment(segment)
            or looks_like_forbidden_subject_text(segment)
            or bool(re.fullmatch(r"(?iu)(?:[ivxlcdmі]+|\d+)\s+група", segment))
            or looks_like_teacher_text(segment.lstrip(". "))
            or _looks_like_latin_teacher_label(segment)
            or _looks_like_compact_teacher_label(segment)
        )
        for segment in segments
    )


def _has_dangling_conjunction_segment(text: str) -> bool:
    segments = [normalize_service_tokens(segment).strip(" .,:;-") for segment in re.split(r"\s*;\s*", text) if normalize_service_tokens(segment).strip(" .,:;-")]
    if not segments:
        return False
    for segment in segments:
        lowered = segment.casefold()
        if lowered in {"та", "і", "й", "and"}:
            return True
        if lowered.endswith((" та", " і", " й", " and")):
            return True
    return False


def _has_lowercase_followup_segment(text: str) -> bool:
    segments = [normalize_service_tokens(segment).strip(" .,:;-") for segment in re.split(r"\s*;\s*", text) if normalize_service_tokens(segment).strip(" .,:;-")]
    if len(segments) < 2:
        return False
    return any(segment[:1].islower() for segment in segments[1:] if segment)


def _looks_like_group_aggregate_program_label(text: str) -> bool:
    segments = [normalize_service_tokens(segment).strip(" .,:;-") for segment in re.split(r"\s*;\s*", text) if normalize_service_tokens(segment).strip(" .,:;-")]
    if not segments:
        return False
    group_segments = sum(1 for segment in segments if re.search(r"(?iu)\bгрупа\b", segment))
    academic_segments = sum(1 for segment in segments if re.search(r"(?iu)\b(?:акад\w*|к[-\s]*ад\w*)\b", segment))
    numeric_segments = sum(1 for segment in segments if re.fullmatch(r"\d+", segment))
    stream_segments = sum(1 for segment in segments if re.search(r"(?iu)\b(?:[ivxlcdm]+|\d+)\s*потік\b", segment))
    if group_segments >= 2:
        return True
    if stream_segments >= 1 and group_segments >= 1:
        return True
    if academic_segments >= 1 and (numeric_segments >= 1 or len(segments) >= 2):
        return True
    return False


def _looks_like_room_label_fragment(value: str) -> bool:
    cleaned = normalize_service_tokens(value)
    if not cleaned:
        return False
    if ROOM_LABEL_FRAGMENT_RE.fullmatch(cleaned):
        return True
    return bool(re.fullmatch(r"(?iu)\d{2,4}(?:[-/][\u0430-\u044f\u0456\u0457\u0454\u0491a-z])", cleaned))


def _looks_like_compact_teacher_label(value: str) -> bool:
    cleaned = normalize_service_tokens(value).lstrip(". ").strip()
    if not cleaned:
        return False
    if COMPACT_TEACHER_LABEL_RE.fullmatch(cleaned):
        return True
    return bool(
        re.fullmatch(
            r"(?u)^[\u0410-\u042f\u0406\u0407\u0404\u0490][\u0430-\u044f\u0456\u0457\u0454\u0491'\u2019\u02bc-]+"
            r"(?:\s+[\u0410-\u042f\u0406\u0407\u0404\u0490][\u0430-\u044f\u0456\u0457\u0454\u0491'\u2019\u02bc-]+)?"
            r"\s+[\u0410-\u042f\u0406\u0407\u0404\u0490]\.(?:\s*[\u0410-\u042f\u0406\u0407\u0404\u0490]\.?)?$",
            cleaned,
        )
    )


def _looks_like_latin_teacher_label(value: str) -> bool:
    cleaned = normalize_service_tokens(value).lstrip(". ").strip()
    if not cleaned:
        return False
    if re.match(r"(?iu)^(?:dr|prof|professor|associate professor|assistant|lecturer)\.?\s+", cleaned):
        return bool(
            re.fullmatch(
                r"(?u)(?:(?:dr|prof|professor|associate professor|assistant|lecturer)\.?\s+)"
                r"[A-Z][A-Za-z'\u2019\u02bc-]+(?:\s+[A-Z][A-Za-z'\u2019\u02bc-]+){1,3}",
                cleaned,
            )
        )
    return False


def _looks_like_month_only_program_label(value: str) -> bool:
    cleaned = normalize_service_tokens(value).casefold()
    if not cleaned:
        return False
    tokens = [token for token in re.split(r"[^0-9a-z\u0430-\u044f\u0456\u0457\u0454\u0491]+", cleaned) if token]
    if not tokens:
        return False
    month_stems = (
        "січ",
        "лют",
        "берез",
        "квіт",
        "трав",
        "черв",
        "лип",
        "серп",
        "верес",
        "жовт",
        "листоп",
        "груд",
    )
    return all(any(token.startswith(stem) for stem in month_stems) for token in tokens)


def _looks_like_date_week_program_label(value: str) -> bool:
    cleaned = normalize_service_tokens(value).casefold()
    if not cleaned:
        return False
    has_month = any(stem in cleaned for stem in ("січ", "лют", "берез", "квіт", "трав", "черв", "лип", "серп", "верес", "жовт", "листоп", "груд"))
    has_week = "тиж" in cleaned
    has_digits = bool(re.search(r"\d", cleaned))
    return has_month and has_week and has_digits


def _looks_like_cohort_label(text: str) -> bool:
    cleaned = normalize_service_tokens(text)
    if not cleaned:
        return False
    words = re.findall(r"(?u)[A-Za-zА-ЯІЇЄҐа-яіїєґ'’ʼ-]{3,}", cleaned)
    if len(words) < 2:
        return False
    if not re.search(r"\d", cleaned):
        return False
    if looks_like_technical_label(cleaned) or looks_like_urlish_text(cleaned):
        return False
    return True


def count_program_codes(value: Any) -> int:
    text = normalize_service_tokens(value)
    if not text:
        return 0
    return len(PROGRAM_CODE_RE.findall(text))


def looks_like_spaced_weekday_label(value: Any) -> bool:
    text = normalize_service_tokens(value)
    if not text or " " not in text:
        return False
    compact = re.sub(r"\s+", "", text).casefold()
    return compact in SPACED_WEEKDAY_LABELS


def slugify_filename(value: str, fallback: str = "untitled") -> str:
    text = unicodedata.normalize("NFC", value)
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
    text = flatten_multiline(value)
    if not text:
        return False
    if re.search(r"(?iu)\b(?:\u0430\u0443\u0434\.?\s*[\w./-]+|\u0430\u0443\u0434\u0438\u0442\u043e\u0440(?:\u0456\u044f|i\u044f)\s*[\w./-]+|\u043a\u0430\u0431\.?\s*[\w./-]+|online|\u043e\u043d\u043b\u0430\u0439\u043d)\b", text):
        return True
    return bool(
        re.search(
            r"(?iu)\b(?:\u043a\u043e\u0440\u043f\u0443\u0441\s*[\dA-Za-z\u0410-\u042f\u0406\u0407\u0404\u0490./-]+|\u043a\u043e\u0440\u043f\.\s*[\dA-Za-z\u0410-\u042f\u0406\u0407\u0404\u0490./-]+|\u043a\u043e\u0440\u043f\s+\d[\dA-Za-z\u0410-\u042f\u0406\u0407\u0404\u0490./-]*)",
            text,
        )
    )


def looks_like_teacher_text(value: Any) -> bool:
    return bool(TEACHER_TEXT_RE.search(flatten_multiline(value)))


def looks_like_service_text(value: Any) -> bool:
    text = flatten_multiline(value)
    if not text:
        return False
    lowered = text.casefold()
    if looks_like_spaced_weekday_label(text):
        return True
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


def looks_like_forbidden_subject_text(value: Any) -> bool:
    text = normalize_service_tokens(value)
    if not text:
        return False
    if looks_like_spaced_weekday_label(text):
        return True
    return any(pattern.fullmatch(text) for pattern in FORBIDDEN_SUBJECT_PATTERNS)


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
        if looks_like_bad_program_label(text):
            continue
        if is_meaningful_label(text):
            return text
    return ""


def truncate_sheet_title(value: str) -> str:
    text = flatten_multiline(value) or "Аркуш1"
    text = re.sub(r"[:\\/?*\[\]]+", " ", text)
    text = normalize_whitespace(text)
    return text[:31]
