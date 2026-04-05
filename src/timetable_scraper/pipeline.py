from __future__ import annotations

import requests

from .adapters import parse_asset
from .discovery import discover_source, discover_sources
from .export import export_rows
from .fetch import fetch_asset
from .models import AppConfig, PipelineOutput
from .normalize import normalize_document
from .qa import partition_rows


def run_pipeline(config: AppConfig) -> PipelineOutput:
    session = requests.Session()
    discovery = discover_sources(config.sources, session=session)
    normalized_rows = []
    for asset in discovery.assets:
        try:
            fetched = fetch_asset(asset, session=session, cache_dir=config.cache_dir)
            parsed = parse_asset(fetched, ocr_enabled=config.ocr_enabled)
            normalized_rows.extend(normalize_document(parsed))
        except Exception:
            continue
    accepted, review = partition_rows(normalized_rows, threshold=config.confidence_threshold)
    exported_files, manifest_path, review_queue_path = export_rows(
        accepted,
        review,
        template_path=config.template_path,
        output_dir=config.output_dir,
    )
    return PipelineOutput(
        exported_files=exported_files,
        manifest_path=manifest_path,
        review_queue_path=review_queue_path,
        rows=accepted,
        review_rows=review,
    )


def inspect_config_source(config: AppConfig, source_name: str | None = None) -> str:
    session = requests.Session()
    chunks: list[str] = []
    for source in config.sources:
        if source_name and source.name != source_name:
            continue
        result = discover_source(source, session=session)
        chunks.append(f"[{source.name}] kind={source.kind} assets={len(result.assets)} issues={len(result.issues)}")
        for asset in result.assets:
            chunks.append(f"  - {asset.asset_kind}: {asset.locator}")
        for issue in result.issues:
            chunks.append(f"  ! {issue.reason} ({issue.locator or 'n/a'})")
    return "\n".join(chunks)
