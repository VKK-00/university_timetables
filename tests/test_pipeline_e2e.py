from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from timetable_scraper.config import load_config
from timetable_scraper.pipeline import run_pipeline


def test_pipeline_runs_against_real_archive(tmp_path: Path) -> None:
    config_path = Path("config/sources.yaml").resolve()
    config = load_config(config_path)
    config.output_dir = tmp_path / "out"
    config.cache_dir = tmp_path / "cache"
    result = run_pipeline(config)
    assert result.exported_files
    assert result.manifest_path.exists()
    assert result.review_queue_path.exists()
    sample_workbook = load_workbook(result.exported_files[0])
    assert sample_workbook.sheetnames
    assert result.rows
