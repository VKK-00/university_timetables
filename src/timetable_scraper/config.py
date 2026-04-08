from __future__ import annotations

from pathlib import Path

import yaml

from .models import AppConfig, ManualAssetSeed, SourceConfig


DEFAULT_KEYWORDS = ["розклад", "schedule", "занять", "пари", "semester", "lessons", "timetable"]


def _resolve_path(base_dir: Path, raw: str | None) -> Path | None:
    if raw is None:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path


def _resolve_required_path(base_dir: Path, raw: str | None, *, field_name: str) -> Path:
    path = _resolve_path(base_dir, raw)
    if path is None:
        raise ValueError(f"Config field '{field_name}' is required")
    return path


def _load_manual_assets(manual_assets_path: Path | None) -> dict[str, list[ManualAssetSeed]]:
    if manual_assets_path is None:
        return {}
    payload = yaml.safe_load(manual_assets_path.read_text(encoding="utf-8")) or {}
    sources_block = payload.get("sources", {})
    if not isinstance(sources_block, dict):
        raise ValueError("manual_assets file must contain a top-level 'sources' mapping")
    result: dict[str, list[ManualAssetSeed]] = {}
    for source_name, items in sources_block.items():
        if not isinstance(source_name, str):
            raise ValueError("manual_assets source names must be strings")
        if not isinstance(items, list):
            raise ValueError(f"manual_assets for source '{source_name}' must be a list")
        result[source_name] = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                raise ValueError(f"manual_assets entries for source '{source_name}' must include a string 'url'")
            result[source_name].append(
                ManualAssetSeed(
                    url=item["url"],
                    display_name=str(item.get("display_name", "")),
                    asset_kind=str(item.get("asset_kind", "file_url")),
                )
            )
    return result


def load_config(config_path: str | Path) -> AppConfig:
    config_path = Path(config_path).resolve()
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    base_dir = config_path.parent
    manual_assets_path = _resolve_path(base_dir, data.get("manual_assets_path"))
    manual_assets = _load_manual_assets(manual_assets_path)
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
            manual_assets=list(manual_assets.get(item.get("name", f"source-{index}"), [])),
        )
        for index, item in enumerate(data.get("sources", []), start=1)
    ]
    return AppConfig(
        template_path=_resolve_required_path(base_dir, data.get("template_path"), field_name="template_path"),
        output_dir=_resolve_required_path(base_dir, data.get("output_dir", "out"), field_name="output_dir"),
        cache_dir=_resolve_required_path(base_dir, data.get("cache_dir", ".cache/timetable_scraper"), field_name="cache_dir"),
        confidence_threshold=float(data.get("confidence_threshold", 0.74)),
        ocr_enabled=bool(data.get("ocr_enabled", True)),
        sources=sources,
        manual_assets_path=manual_assets_path,
    )
