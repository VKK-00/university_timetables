from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import requests  # type: ignore[import-untyped]

from .adapters import parse_asset
from .discovery import discover_source, discover_sources
from .export import export_rows, write_autofix_report
from .fetch import fetch_asset
from .models import AppConfig, PipelineOutput
from .normalize import normalize_document
from .qa import audit_exported_workbooks, partition_rows, refine_group_quality, sanitize_export_rows
from .reporting import (
    build_source_summaries,
    load_previous_source_summaries,
    write_review_summary,
    write_run_delta,
    write_source_summaries,
)


def run_pipeline(config: AppConfig) -> PipelineOutput:
    session = requests.Session()
    previous_summaries = load_previous_source_summaries(config.output_dir)
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
    accepted, review = refine_group_quality(accepted, review)
    accepted, review = sanitize_export_rows(accepted, review)
    _prepare_output_dir(config.output_dir)
    exported_files, manifest_path, review_queue_path = export_rows(
        accepted,
        review,
        template_path=config.template_path,
        output_dir=config.output_dir,
    )
    review_summary_json_path, review_summary_xlsx_path = write_review_summary(review, output_dir=config.output_dir)
    autofix_report_json_path, autofix_report_xlsx_path, autofix_rows = write_autofix_report(
        [*accepted, *review],
        output_dir=config.output_dir,
    )
    workbook_qa, qa_report_json_path, qa_report_xlsx_path = audit_exported_workbooks(
        exported_files,
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
    run_delta_path = write_run_delta(source_summaries, previous_summaries, output_dir=config.output_dir)
    return PipelineOutput(
        exported_files=exported_files,
        manifest_path=manifest_path,
        review_queue_path=review_queue_path,
        rows=accepted,
        review_rows=review,
        source_summary_path=source_summary_path,
        source_report_path=source_report_path,
        review_summary_json_path=review_summary_json_path,
        review_summary_xlsx_path=review_summary_xlsx_path,
        run_delta_path=run_delta_path,
        autofix_report_json_path=autofix_report_json_path,
        autofix_report_xlsx_path=autofix_report_xlsx_path,
        autofix_rows=autofix_rows,
        qa_report_json_path=qa_report_json_path,
        qa_report_xlsx_path=qa_report_xlsx_path,
        qa_failures=sum(1 for item in workbook_qa if item.status == "fail"),
        qa_warnings=sum(1 for item in workbook_qa if item.status == "warning"),
        workbook_qa=workbook_qa,
        source_summaries=source_summaries,
    )


def _prepare_output_dir(output_dir: Path) -> None:
    if not output_dir.exists():
        return
    for path in sorted(output_dir.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            try:
                path.rmdir()
            except OSError:
                continue


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
