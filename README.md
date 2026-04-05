# university_timetables

`university_timetables` is a KNU-first university timetable scraper. It collects schedules from local folders and ZIP archives, faculty websites, public Google Sheets and Google Drive assets, direct file links, HTML tables, and PDF files with OCR fallback, then exports normalized Excel workbooks based on [`Шаблон.xlsx`](./Шаблон.xlsx).

`university_timetables` це KNU-first скрепер університетських розкладів. Він тягне розклади з локальних папок і ZIP-архівів, сайтів факультетів, публічних Google Sheets і Google Drive, прямих посилань на файли, HTML-таблиць і PDF з OCR fallback, а потім експортує нормалізовані Excel-файли на основі [`Шаблон.xlsx`](./Шаблон.xlsx).

## Overview / Огляд

- Fixed pipeline: `discover -> fetch -> parse -> normalize -> validate/confidence -> export`.
- Main CLI entrypoints: `doctor`, `inspect-source`, `run`.
- Output format is template-driven: row 1 contains the program title, row 2 contains headers, row 3+ contains normalized rows.
- The project is intentionally KNU-first. It does not claim that every KNU source is fully parseable today.
- For official sources that are unavailable or technically unsuitable, the scraper now produces an explicit final status instead of silent zero-row output.

## What It Ingests / Що вміє тягнути

- Local folders with timetable files
- ZIP archives without manual unpacking into tracked files
- Direct Excel files: `.xlsx`, `.xlsm`, `.xls`
- Public Google Sheets and Google Drive assets
- Faculty and institute web pages with link discovery
- HTML tables and simple schedule-like blocks
- PDF files with text extraction first and OCR fallback via Tesseract

## Current KNU Coverage / Поточне покриття КНУ

Latest full KNU web run source of truth:
- `46080` accepted rows
- `954` review rows

Parsed sources:
- `Geo`
- `Econom`
- `History`
- `Mechmat`
- `FIT`
- `Psychology`
- `Sociology`
- `Physics`
- `Chemistry`
- `Geology`
- `Biomed`

Confirmed blockers:
- `CSC`
- `REX`
- `Philosophy`
- `Law`
- `Military`
- `IHT`
- `IIR`
- `Journalism`
- `Philology`

FIT-specific note:
- `FIT: 26928 accepted, 954 review`

Detailed coverage and source-level status are documented in:
- [`reports/knu_web_run_2026-04-05.md`](./reports/knu_web_run_2026-04-05.md)
- [`out_knu_web/source_summary.md`](./out_knu_web/source_summary.md)

The current best-possible state is: the system can run across all configured KNU sources and assign each one a final status, but not every official source currently yields a complete schedule.

## Quick Start

Install the project and development dependencies:

```powershell
pip install -e .[dev]
```

Verify the environment, including OCR dependencies:

```powershell
python -m timetable_scraper doctor
```

Inspect discovered assets for a config before a full run:

```powershell
python -m timetable_scraper inspect-source --config config/sources.yaml
```

Run the main pipeline:

```powershell
python -m timetable_scraper run --config config/sources.yaml
```

Run the KNU web coverage config:

```powershell
python -m timetable_scraper run --config config/knu_web_schedule.yaml
```

## Config

The main config file contains:

- `template_path`
- `output_dir`
- `cache_dir`
- `confidence_threshold`
- `ocr_enabled`
- `sources[]`

Supported `sources[].kind` values:

- `folder`
- `zip`
- `web_page`
- `file_url`
- `google_sheet`

Example:

```yaml
template_path: ../Шаблон.xlsx
output_dir: ../out
cache_dir: ../.cache/timetable_scraper
confidence_threshold: 0.74
ocr_enabled: true
sources:
  - name: knu-archive
    kind: zip
    path: ../Розклади КНУ Шевченка _ Univera-20260404T113654Z-3-001.zip
  - name: faculty-page
    kind: web_page
    url: https://example.edu/faculty/schedule
    allow_domains: [example.edu]
    schedule_keywords: [розклад, schedule, занять, курс]
    follow_links_depth: 0
  - name: public-sheet
    kind: google_sheet
    url: https://docs.google.com/spreadsheets/d/.../edit#gid=0
```

## Outputs

- `out/<faculty>/<program>.xlsx`: normalized schedule workbooks exported in the template layout
- `out/manifest.jsonl`: one JSON line per exported row with provenance, warnings, confidence, and content hash
- `out/review_queue.xlsx`: low-confidence or incomplete rows that require manual review
- `out_knu_web/source_summary.md`: source-level status summary for the KNU web run
- `out_knu_web/source_summary.json`: machine-readable source-level status summary

## OCR Requirements

The PDF pipeline uses Tesseract with `ukr` and `eng` language data.

Expected stack:
- `pytesseract`
- `pypdfium2`
- local Tesseract binary available on `PATH`
- `ukr` and `eng` traineddata installed

Use:

```powershell
python -m timetable_scraper doctor
```

If OCR dependencies are missing, `doctor` should fail explicitly and `run` should not silently continue with incomplete OCR support.

## Known Limitations

- Some official sources return `HTTP 500`.
- Some official sources are blocked by `403 / Cloudflare`.
- Some public storage links, especially OneDrive-based sources, may block public download.
- Some published PDF or linked assets do not yield complete rows even after text extraction and OCR.
- The scraper is KNU-first and coverage is intentionally reported honestly as `parsed` or `confirmed-blocker`; it does not force low-quality output for blocked sources.

## Development and Tests

Run the regression suite:

```powershell
pytest -q
```

Useful commands during development:

```powershell
python -m timetable_scraper doctor
python -m timetable_scraper inspect-source --config config/sources.yaml
python -m timetable_scraper run --config config/sources.yaml
python -m timetable_scraper run --config config/knu_web_schedule.yaml
```

## Repository Metadata / Метадані репозиторію

GitHub repository description and topics are not updated automatically from this environment. Apply the following values manually in the GitHub UI.

GitHub description:

```text
KNU-first university timetable scraper with Excel, web, Google Sheets/Drive, and PDF/OCR ingestion plus normalized Excel export.
```

GitHub topics:

```text
python, timetable, schedule, scraper, web-scraping, ocr, pdf, excel, google-sheets, education, university, knu
```
