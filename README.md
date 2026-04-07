# university_timetables

`university_timetables` is a KNU-first university timetable scraper. It collects schedules from local folders and ZIP archives, faculty websites, public Google Sheets and Google Drive assets, direct file links, HTML tables, and PDF files with OCR fallback, then exports normalized Excel workbooks based on [`Шаблон.xlsx`](./Шаблон.xlsx).

`university_timetables` це KNU-first скрепер університетських розкладів. Він тягне розклади з локальних папок і ZIP-архівів, сайтів факультетів, публічних Google Sheets і Google Drive, прямих посилань на файли, HTML-таблиць і PDF з OCR fallback, а потім експортує нормалізовані Excel-файли на основі [`Шаблон.xlsx`](./Шаблон.xlsx).

## Overview / Огляд

- Fixed pipeline: `discover -> fetch -> parse -> normalize -> validate/confidence -> export -> post-run QA`
- Main CLI entrypoints: `doctor`, `inspect-source`, `run`
- Output format is template-driven: row 1 contains the program title, row 2 contains headers, row 3+ contains normalized rows
- Row-level QA removes broken or ambiguous records from final Excel output and moves them to `review_queue.xlsx`
- Workbook-level QA checks every exported `.xlsx`; `run` keeps outputs but returns non-zero if any workbook fails QA
- The project is intentionally KNU-first. It does not claim that every official KNU source is fully parseable today

## What It Ingests / Що вміє тягнути

- Local folders with timetable files
- ZIP archives without manual unpacking into tracked files
- Direct Excel files: `.xlsx`, `.xlsm`, `.xls`
- Public Google Sheets and Google Drive assets
- Faculty and institute web pages with link discovery
- HTML tables and simple schedule-like blocks
- PDF files with text extraction first and OCR fallback via Tesseract

## Current KNU Coverage / Поточне покриття КНУ

Latest full KNU web run source of truth: April 7, 2026

- `42905` accepted rows
- `9062` review rows
- `0` QA warnings
- `0` QA failures

Current source statuses:

- `parsed`: `Geo`, `Econom`, `History`, `Mechmat`, `FIT`, `Psychology`, `REX`, `Sociology`, `Physics`, `Philosophy`, `Chemistry`, `Law`, `IHT`, `Journalism`, `Geology`, `Biomed`
- `confirmed-blocker`: `CSC`, `Military`, `IIR`
- `review-only`: `Philology`

Largest parsed sources in the current run:

- `FIT: 26793 accepted, 1075 review`
- `Physics: 6605 accepted, 5018 review`
- `Sociology: 3937 accepted, 347 review`

Detailed coverage and source-level status are documented in:

- [`out_knu_web/source_summary.md`](./out_knu_web/source_summary.md)
- [`out_knu_web/source_summary.json`](./out_knu_web/source_summary.json)
- [`out_knu_web/qa_report.json`](./out_knu_web/qa_report.json)
- [`out_knu_web/qa_report.xlsx`](./out_knu_web/qa_report.xlsx)

The current best-possible state is:

- the system runs across all configured KNU sources
- every source gets an explicit final status
- low-quality rows are pushed to review instead of silently exported
- some official sources are still blocked by the source itself or remain only partially parseable

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
- `out/manifest.jsonl`: one JSON line per normalized row with provenance, warnings, confidence, and content hash
- `out/review_queue.xlsx`: rows that failed QA or remained ambiguous after parsing
- `out/qa_report.json`: machine-readable workbook QA summary
- `out/qa_report.xlsx`: readable workbook QA summary
- `out_knu_web/source_summary.md`: source-level status summary for the KNU web run
- `out_knu_web/source_summary.json`: machine-readable source-level status summary

## QA Rules / Правила якості

Rows stay in exported Excel only if they have at least:

- `day`
- `start_time`
- `end_time`
- `subject`

Rows are moved to review if they show signs of:

- mixed columns inside `subject`
- room, link, or teacher text still embedded into the wrong field
- admin or service text embedded into schedule rows
- OCR or PDF garbage
- fragmented PDF slot parsing
- implausible or broken time slots
- missing required fields

Additional guarantees in the current pipeline:

- `week_type` is always filled; if no reliable week marker exists, the default is `Обидва`
- `week_source` is preserved in normalized data
- `run` cleans the target output directory before writing a new result set

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

If OCR dependencies are missing, `doctor` fails explicitly and `run` should not continue with incomplete OCR support.

## Known Limitations

- Some official sources still return `HTTP 500`
- Some official sources are blocked by `403 / Cloudflare`
- Some public storage links, especially OneDrive-based sources, block anonymous download
- Some PDFs still parse only partially and therefore produce more review rows than accepted rows
- `review-only` status means the source was reached, but the current parser could not extract a reliable final timetable without lowering quality thresholds

Current non-parsed KNU statuses:

- `confirmed-blocker`: `CSC`, `Law`, `Military`, `IIR`
- `review-only`: `Philology`

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
