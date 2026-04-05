from __future__ import annotations

from pathlib import Path

import yaml

from .models import AppConfig, SourceConfig


DEFAULT_KEYWORDS = ["розклад", "schedule", "занять", "пари", "semester", "lessons", "timetable"]


def _resolve_path(base_dir: Path, raw: str | None) -> Path | None:
    if raw is None:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path


def load_config(config_path: str | Path) -> AppConfig:
    config_path = Path(config_path).resolve()
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    base_dir = config_path.parent
    sources = [
        SourceConfig(
            kind=item["kind"],
            name=item.get("name", f"source-{index}"),
            path=_resolve_path(base_dir, item.get("path")),
            url=item.get("url"),
            recurse=bool(item.get("recurse", True)),
            allow_domains=list(item.get("allow_domains", [])),
            schedule_keywords=list(item.get("schedule_keywords", DEFAULT_KEYWORDS)),
            follow_links_depth=int(item.get("follow_links_depth", 0)),
        )
        for index, item in enumerate(data.get("sources", []), start=1)
    ]
    return AppConfig(
        template_path=_resolve_path(base_dir, data["template_path"]),
        output_dir=_resolve_path(base_dir, data.get("output_dir", "out")),
        cache_dir=_resolve_path(base_dir, data.get("cache_dir", ".cache/timetable_scraper")),
        confidence_threshold=float(data.get("confidence_threshold", 0.74)),
        ocr_enabled=bool(data.get("ocr_enabled", True)),
        sources=sources,
    )
