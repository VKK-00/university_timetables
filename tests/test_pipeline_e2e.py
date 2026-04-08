from __future__ import annotations

from pathlib import Path

import requests
import pytest
from openpyxl import load_workbook

from timetable_scraper.config import load_config
from timetable_scraper.models import AppConfig, DiscoveredAsset, DiscoveryResult, FetchedAsset, NormalizedRow
from timetable_scraper.pipeline import run_pipeline


def test_pipeline_runs_against_real_archive(tmp_path: Path) -> None:
    config_path = Path("config/sources.yaml").resolve()
    config = load_config(config_path)
    if any(source.path and not source.path.exists() for source in config.sources):
        pytest.skip("Real archive fixture is not available in the working tree")
    config.output_dir = tmp_path / "out"
    config.cache_dir = tmp_path / "cache"
    result = run_pipeline(config)
    assert result.exported_files
    assert result.manifest_path.exists()
    assert result.review_queue_path.exists()
    assert result.review_summary_json_path and result.review_summary_json_path.exists()
    assert result.review_summary_xlsx_path and result.review_summary_xlsx_path.exists()
    assert result.run_delta_path and result.run_delta_path.exists()
    assert result.autofix_report_json_path and result.autofix_report_json_path.exists()
    assert result.autofix_report_xlsx_path and result.autofix_report_xlsx_path.exists()
    sample_workbook = load_workbook(result.exported_files[0])
    assert sample_workbook.sheetnames
    assert result.rows


def test_pipeline_skips_unavailable_assets(monkeypatch, tmp_path: Path) -> None:
    config = AppConfig(
        template_path=Path("Шаблон.xlsx").resolve(),
        output_dir=tmp_path / "out",
        cache_dir=tmp_path / "cache",
        confidence_threshold=0.74,
        ocr_enabled=False,
        sources=[],
    )
    bad_asset = DiscoveredAsset(
        source_name="bad",
        source_kind="google_sheet",
        source_url_or_path="https://docs.google.com/spreadsheets/d/bad/edit",
        asset_kind="google_sheet",
        locator="https://docs.google.com/spreadsheets/d/bad/edit",
        display_name="bad",
    )
    good_asset = DiscoveredAsset(
        source_name="good",
        source_kind="google_sheet",
        source_url_or_path="https://docs.google.com/spreadsheets/d/good/edit",
        asset_kind="google_sheet",
        locator="https://docs.google.com/spreadsheets/d/good/edit",
        display_name="good",
    )
    good_fetched = FetchedAsset(
        asset=good_asset,
        content=b"",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content_hash="good",
        resolved_locator="good.xlsx",
    )
    good_row = NormalizedRow(
        program="Demo",
        faculty="FIT",
        week_type="Обидва",
        day="Понеділок",
        start_time="09:30",
        end_time="10:50",
        subject="Алгоритми",
        confidence=1.0,
    )

    def fake_fetch(asset, session, cache_dir):
        if asset.locator == bad_asset.locator:
            raise requests.HTTPError("401")
        return good_fetched

    def fake_export(rows, review_rows, *, template_path, output_dir):
        manifest_path = output_dir / "manifest.jsonl"
        review_path = output_dir / "review_queue.xlsx"
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text("", encoding="utf-8")
        review_path.write_text("", encoding="utf-8")
        exported = output_dir / "demo.xlsx"
        exported.write_text("", encoding="utf-8")
        return [exported], manifest_path, review_path

    monkeypatch.setattr(
        "timetable_scraper.pipeline.discover_sources",
        lambda sources, session: DiscoveryResult(assets=[bad_asset, good_asset], issues=[]),
    )
    monkeypatch.setattr("timetable_scraper.pipeline.fetch_asset", fake_fetch)
    monkeypatch.setattr("timetable_scraper.pipeline.parse_asset", lambda fetched, ocr_enabled: fetched)
    monkeypatch.setattr("timetable_scraper.pipeline.normalize_document", lambda parsed: [good_row])
    monkeypatch.setattr("timetable_scraper.pipeline.export_rows", fake_export)

    result = run_pipeline(config)

    assert len(result.rows) == 1
    assert not result.review_rows
    assert result.exported_files
    assert result.review_summary_json_path and result.review_summary_json_path.exists()
    assert result.review_summary_xlsx_path and result.review_summary_xlsx_path.exists()
    assert result.run_delta_path and result.run_delta_path.exists()
    assert result.autofix_report_json_path and result.autofix_report_json_path.exists()
    assert result.autofix_report_xlsx_path and result.autofix_report_xlsx_path.exists()
    assert result.qa_failures == 1


def test_pipeline_cleans_previous_output_dir(tmp_path: Path, monkeypatch) -> None:
    config = AppConfig(
        template_path=Path("Шаблон.xlsx").resolve(),
        output_dir=tmp_path / "out",
        cache_dir=tmp_path / "cache",
        confidence_threshold=0.74,
        ocr_enabled=False,
        sources=[],
    )
    stale_file = config.output_dir / "stale.txt"
    stale_file.parent.mkdir(parents=True, exist_ok=True)
    stale_file.write_text("old", encoding="utf-8")

    monkeypatch.setattr(
        "timetable_scraper.pipeline.discover_sources",
        lambda sources, session: DiscoveryResult(assets=[], issues=[]),
    )
    monkeypatch.setattr(
        "timetable_scraper.pipeline.export_rows",
        lambda rows, review_rows, *, template_path, output_dir: ([], output_dir / "manifest.jsonl", output_dir / "review_queue.xlsx"),
    )
    monkeypatch.setattr(
        "timetable_scraper.pipeline.write_autofix_report",
        lambda rows, *, output_dir: (output_dir / "autofix_report.json", output_dir / "autofix_report.xlsx", 0),
    )
    monkeypatch.setattr(
        "timetable_scraper.pipeline.audit_exported_workbooks",
        lambda exported_files, output_dir: ([], output_dir / "qa_report.json", output_dir / "qa_report.xlsx"),
    )
    monkeypatch.setattr(
        "timetable_scraper.pipeline.write_source_summaries",
        lambda summaries, *, output_dir: (output_dir / "source_summary.json", output_dir / "source_summary.md"),
    )

    run_pipeline(config)

    assert not stale_file.exists()
