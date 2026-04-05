from __future__ import annotations

from collections import Counter, defaultdict

import requests

from .adapters import parse_asset
from .discovery import discover_source, discover_sources
from .export import export_rows
from .fetch import fetch_asset
from .models import AppConfig, PipelineOutput
from .normalize import normalize_document
from .qa import partition_rows
from .reporting import build_source_summaries, write_source_summaries


def run_pipeline(config: AppConfig) -> PipelineOutput:
    session = requests.Session()
    discovery = discover_sources(config.sources, session=session)
    normalized_rows = []
    attempted_assets: Counter[str] = Counter()
    runtime_issues: dict[str, list[str]] = defaultdict(list)

    for asset in discovery.assets:
        attempted_assets[asset.source_name] += 1
        try:
            fetched = fetch_asset(asset, session=session, cache_dir=config.cache_dir)
            parsed = parse_asset(fetched, ocr_enabled=config.ocr_enabled)
            rows = normalize_document(parsed)
            normalized_rows.extend(rows)
            if not rows and parsed.warnings:
                runtime_issues[asset.source_name].extend(parsed.warnings)
        except Exception as exc:
            runtime_issues[asset.source_name].append(f"{exc.__class__.__name__}: {exc}")

    accepted, review = partition_rows(normalized_rows, threshold=config.confidence_threshold)
    exported_files, manifest_path, review_queue_path = export_rows(
        accepted,
        review,
        template_path=config.template_path,
        output_dir=config.output_dir,
    )
    source_summaries = build_source_summaries(
        config.sources,
        discovery,
        accepted,
        review,
        attempted_assets=attempted_assets,
        runtime_issues=runtime_issues,
    )
    source_summary_path, source_report_path = write_source_summaries(source_summaries, output_dir=config.output_dir)
    return PipelineOutput(
        exported_files=exported_files,
        manifest_path=manifest_path,
        review_queue_path=review_queue_path,
        rows=accepted,
        review_rows=review,
        source_summary_path=source_summary_path,
        source_report_path=source_report_path,
        source_summaries=source_summaries,
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
            chunks.append(
                f"  - {asset.asset_kind} origin={asset.origin_kind} root={asset.source_root_url} locator={asset.locator}"
            )
        for issue in result.issues:
            chunks.append(f"  ! {issue.reason} ({issue.locator or 'n/a'})")
    return "\n".join(chunks)
