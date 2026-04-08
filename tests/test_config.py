from __future__ import annotations

from pathlib import Path

from timetable_scraper.config import load_config


def test_load_config_attaches_manual_assets_to_sources(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    manual_assets_path = tmp_path / "manual_assets.yaml"
    template_path = Path("Шаблон.xlsx").resolve()
    manual_assets_path.write_text(
        """
sources:
  iir-schedule:
    - url: https://example.edu/direct/iir.xlsx
      display_name: Direct IIR workbook
      asset_kind: file_url
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config_path.write_text(
        f"""
template_path: {template_path.as_posix()}
output_dir: out
cache_dir: cache
ocr_enabled: false
manual_assets_path: {manual_assets_path.name}
sources:
  - name: iir-schedule
    kind: web_page
    url: https://www.iir.edu.ua/rozklad
  - name: phys-schedule
    kind: web_page
    url: https://phys.knu.ua/navchannya/rozklad-zanyat?ad
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = load_config(config_path)

    iir_source = next(source for source in config.sources if source.name == "iir-schedule")
    phys_source = next(source for source in config.sources if source.name == "phys-schedule")
    assert config.manual_assets_path == manual_assets_path.resolve()
    assert len(iir_source.manual_assets) == 1
    assert iir_source.manual_assets[0].url == "https://example.edu/direct/iir.xlsx"
    assert iir_source.manual_assets[0].display_name == "Direct IIR workbook"
    assert not phys_source.manual_assets
