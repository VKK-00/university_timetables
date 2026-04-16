from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

import requests  # type: ignore[import-untyped]

from .adapters import parse_asset
from .discovery import discover_source, discover_sources
from .export import export_rows, write_autofix_report
from .fetch import build_http_session, fetch_asset
from .models import (
    AppConfig,
    DiscoveredAsset,
    DiscoveryIssue,
    DiscoveryResult,
    NormalizedRow,
    PipelineOutput,
    SourceConfig,
    SourceRunSummary,
)
from .normalize import normalize_document
from .qa import audit_exported_workbooks, partition_rows, refine_group_quality, sanitize_export_rows
from .reporting import (
    build_source_summaries,
    load_previous_source_summaries,
    write_review_summary,
    write_run_delta,
    write_source_summaries,
)


@dataclass(slots=True)
class PipelineAccumulation:
    discovery_assets: list[DiscoveredAsset] = field(default_factory=list)
    discovery_issues: list[DiscoveryIssue] = field(default_factory=list)
    normalized_rows: list[NormalizedRow] = field(default_factory=list)
    attempted_assets: Counter[str] = field(default_factory=Counter)
    runtime_issues: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    def extend(self, other: "PipelineAccumulation") -> None:
        self.discovery_assets.extend(other.discovery_assets)
        self.discovery_issues.extend(other.discovery_issues)
        self.normalized_rows.extend(other.normalized_rows)
        self.attempted_assets.update(other.attempted_assets)
        for source_name, issues in other.runtime_issues.items():
            self.runtime_issues[source_name].extend(issues)


def run_pipeline(config: AppConfig) -> PipelineOutput:
    previous_summaries = load_previous_source_summaries(config.output_dir)
    with build_http_session() as session:
        accumulation = _collect_pipeline_batch(config, config.sources, session=session)
    return _finalize_pipeline_run(config, accumulation, previous_summaries=previous_summaries)


def run_pipeline_batched(
    config: AppConfig,
    *,
    batch_size: int = 5,
    merge_existing: bool = False,
    summary_sources: list[SourceConfig] | None = None,
) -> PipelineOutput:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    previous_summaries = load_previous_source_summaries(config.output_dir)
    accumulation = PipelineAccumulation()
    refreshed_source_names = {source.name for source in config.sources}
    preserved_source_names: set[str] = set()
    if merge_existing:
        existing_rows = _load_existing_manifest_rows(config.output_dir, exclude_source_names=refreshed_source_names)
        preserved_source_names = set(previous_summaries) - refreshed_source_names
        accumulation.normalized_rows.extend(existing_rows)
    with build_http_session() as session:
        for source_batch in _iter_source_batches(config.sources, batch_size=batch_size):
            accumulation.extend(_collect_pipeline_batch(config, source_batch, session=session))
    return _finalize_pipeline_run(
        config,
        accumulation,
        previous_summaries=previous_summaries,
        summary_sources=summary_sources,
        preserved_source_names=preserved_source_names,
    )


def _collect_pipeline_batch(
    config: AppConfig,
    sources: list[SourceConfig],
    *,
    session: requests.Session,
) -> PipelineAccumulation:
    discovery = discover_sources(list(sources), session=session)
    accumulation = PipelineAccumulation(
        discovery_assets=list(discovery.assets),
        discovery_issues=list(discovery.issues),
    )

    for asset in discovery.assets:
        accumulation.attempted_assets[asset.source_name] += 1
        try:
            fetched = fetch_asset(asset, session=session, cache_dir=config.cache_dir)
            parsed = parse_asset(fetched, ocr_enabled=config.ocr_enabled)
            rows = normalize_document(parsed)
            accumulation.normalized_rows.extend(rows)
            if not rows and parsed.warnings:
                accumulation.runtime_issues[asset.source_name].extend(parsed.warnings)
        except Exception as exc:
            accumulation.runtime_issues[asset.source_name].append(f"{exc.__class__.__name__}: {exc}")
    return accumulation


def _finalize_pipeline_run(
    config: AppConfig,
    accumulation: PipelineAccumulation,
    *,
    previous_summaries,
    summary_sources: list[SourceConfig] | None = None,
    preserved_source_names: set[str] | None = None,
) -> PipelineOutput:
    discovery = DiscoveryResult(
        assets=list(accumulation.discovery_assets),
        issues=list(accumulation.discovery_issues),
    )
    accepted, review = partition_rows(accumulation.normalized_rows, threshold=config.confidence_threshold)
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
        summary_sources or config.sources,
        discovery,
        accepted,
        review,
        attempted_assets=accumulation.attempted_assets,
        runtime_issues=accumulation.runtime_issues,
    )
    if preserved_source_names:
        _apply_previous_source_metadata(source_summaries, previous_summaries, preserved_source_names)
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


def _iter_source_batches(sources: list[SourceConfig], *, batch_size: int):
    for index in range(0, len(sources), batch_size):
        yield sources[index : index + batch_size]


def _load_existing_manifest_rows(output_dir: Path, *, exclude_source_names: set[str]) -> list[NormalizedRow]:
    manifest_path = output_dir / "manifest.jsonl"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Cannot merge existing output because manifest is missing: {manifest_path}")
    rows: list[NormalizedRow] = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            continue
        source_name = str(payload.get("source_name") or "")
        if source_name in exclude_source_names:
            continue
        rows.append(_normalized_row_from_manifest_payload(payload))
    return rows


def _normalized_row_from_manifest_payload(payload: dict[str, Any]) -> NormalizedRow:
    fields = NormalizedRow.__dataclass_fields__
    list_fields = {"warnings", "autofix_actions", "qa_flags"}
    kwargs: dict[str, Any] = {}
    for field_name in fields:
        value = payload.get(field_name)
        if field_name in list_fields:
            kwargs[field_name] = [str(item) for item in value] if isinstance(value, list) else []
        elif field_name == "confidence":
            kwargs[field_name] = float(value) if isinstance(value, (int, float)) else 1.0
        elif value is None:
            continue
        else:
            kwargs[field_name] = str(value)
    return NormalizedRow(**kwargs)


def _apply_previous_source_metadata(
    summaries: list[SourceRunSummary],
    previous_summaries: dict[str, dict[str, Any]],
    preserved_source_names: set[str],
) -> None:
    for summary in summaries:
        if summary.source_name not in preserved_source_names:
            continue
        previous = previous_summaries.get(summary.source_name)
        if not previous:
            continue
        summary.status = str(previous.get("status") or summary.status)
        summary.note = str(previous.get("note") or summary.note)
        summary.discovered_assets = _int_from_previous(previous, "discovered_assets", summary.discovered_assets)
        summary.attempted_assets = _int_from_previous(previous, "attempted_assets", summary.attempted_assets)
        summary.discovery_issues = _list_from_previous(previous, "discovery_issues", summary.discovery_issues)
        summary.runtime_issues = _list_from_previous(previous, "runtime_issues", summary.runtime_issues)


def _int_from_previous(payload: dict[str, Any], key: str, fallback: int) -> int:
    value = payload.get(key)
    return int(value) if isinstance(value, (int, float)) else fallback


def _list_from_previous(payload: dict[str, Any], key: str, fallback: list[str]) -> list[str]:
    value = payload.get(key)
    return [str(item) for item in value] if isinstance(value, list) else fallback


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
    session = build_http_session()
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
