# university_timetables

`university_timetables` is a KNU-first timetable scraper. It collects schedules from local files, faculty websites, public Google Sheets and Google Drive assets, direct file links, HTML tables, and PDFs with OCR fallback, then exports normalized Excel workbooks based on [`Шаблон.xlsx`](./Шаблон.xlsx).

`university_timetables` це KNU-first скрепер університетських розкладів. Він тягне розклади з локальних файлів, сайтів факультетів, публічних Google Sheets і Google Drive, прямих посилань на файли, HTML-таблиць і PDF з OCR fallback, а потім експортує нормалізовані Excel-книги на основі [`Шаблон.xlsx`](./Шаблон.xlsx).

## Overview / Огляд

- Fixed pipeline: `discover -> fetch -> parse -> normalize -> validate/confidence -> export -> post-run QA`
- Main CLI entrypoints: `doctor`, `inspect-source`, `run`, `run-batched`
- Output is template-driven: row 1 contains the program title, row 2 contains headers, row 3+ contains normalized rows
- Row-level QA keeps broken or ambiguous rows out of exported Excel and moves them into `review_queue.xlsx`
- Autofixes are tracked per row and written into dedicated reports
- Workbook-level QA checks every exported `.xlsx`; `run` writes outputs but returns non-zero only when there are QA failures
- The project is intentionally KNU-first. It does not claim that every official KNU source is always fully parseable

## What It Ingests / Що вміє тягнути

- Local folders with timetable files
- ZIP archives without manual unpacking into tracked files
- Direct Excel files: `.xlsx`, `.xlsm`, `.xls`
- Public Google Sheets and Google Drive assets
- Faculty and institute web pages with link discovery
- HTML tables and simple schedule-like blocks
- PDF files with text extraction first and OCR fallback via Tesseract
- Optional manually seeded official direct assets through `manual_assets.yaml`

## Current KNU Coverage / Поточне покриття КНУ

Latest full KNU web run source of truth: April 13, 2026

- `172` exported workbooks
- `42715` accepted rows
- `3913` review rows
- `46538` rows with autofixes
- `0` QA warnings
- `0` QA failures

Current source statuses:

- `parsed`: `Geo`, `Econom`, `History`, `FIT`, `Psychology`, `REX`, `Sociology`, `Physics`, `Philosophy`, `Chemistry`, `Law`, `Journalism`, `Geology`, `Biomed`
- `confirmed-blocker`: `Mechmat`, `CSC`, `Military`, `IHT`, `IIR`, `Philology`
- `review-only`: none

Largest parsed sources in the current run:

- `FIT: 30053 accepted, 451 review`
- `Physics: 4878 accepted, 979 review`
- `Sociology: 2527 accepted, 725 review`

Detailed coverage and source-level status are documented in:

- [`out_knu_web/source_summary.md`](./out_knu_web/source_summary.md)
- [`out_knu_web/source_summary.json`](./out_knu_web/source_summary.json)
- [`out_knu_web/review_summary.json`](./out_knu_web/review_summary.json)
- [`out_knu_web/review_summary.xlsx`](./out_knu_web/review_summary.xlsx)
- [`out_knu_web/run_delta.json`](./out_knu_web/run_delta.json)
- [`out_knu_web/qa_report.json`](./out_knu_web/qa_report.json)
- [`out_knu_web/qa_report.xlsx`](./out_knu_web/qa_report.xlsx)

Current best-possible state:

- the system runs across all configured KNU sources
- every source gets an explicit final status
- low-quality rows are pushed to review instead of silently exported
- manual official direct assets can be seeded when a source page is blocked but an official file is known
- some official sources are still blocked by the source itself and remain `confirmed-blocker`

## Quick Start

Install the project and development dependencies:

```powershell
pip install -e .[dev]
```

Verify the environment, including OCR dependencies:

```powershell
python -m timetable_scraper doctor
```

Inspect discovered assets before a full run:

```powershell
python -m timetable_scraper inspect-source --config config/sources.yaml
```

Run the main pipeline:

```powershell
python -m timetable_scraper run --config config/sources.yaml
```

Run the full KNU web coverage config:

```powershell
python -m timetable_scraper run --config config/knu_web_schedule.yaml
```

Run the same config in segmented batches to avoid long single-pass runs:

```powershell
python -m timetable_scraper run-batched --config config/knu_web_schedule.yaml --batch-size 5
```

Run the focused smoke set for the most failure-prone KNU sources:

```powershell
python -m timetable_scraper run-batched --config config/knu_web_smoke.yaml --batch-size 3
```

## Config

The main config file contains:

- `template_path`
- `output_dir`
- `cache_dir`
- `confidence_threshold`
- `ocr_enabled`
- `manual_assets_path`
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
manual_assets_path: manual_assets.yaml
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

Manual official asset seeding:

- `config/manual_assets.yaml` is optional
- it is intended for cases where the official source page is blocked or unstable, but an official direct XLSX/PDF link is known
- seeded assets keep the original `source_root_url` provenance and are marked as `manual_seed` in discovery
- example structure is provided in [`config/manual_assets.example.yaml`](./config/manual_assets.example.yaml)

## Outputs

- `out/<faculty>/<program>.xlsx`: normalized schedule workbooks exported in the template layout
- `out/manifest.jsonl`: one JSON line per normalized row with provenance, warnings, confidence, QA flags, and content hash
- `out/review_queue.xlsx`: rows that failed QA or remained ambiguous after parsing
- `out/autofix_report.json`: machine-readable summary of autofix actions applied during normalization
- `out/autofix_report.xlsx`: readable autofix summary and per-row autofix trace
- `out/qa_report.json`: machine-readable workbook QA summary
- `out/qa_report.xlsx`: readable workbook QA summary
- `out/review_summary.json`: machine-readable aggregation of review backlog by source, warning, and QA flag
- `out/review_summary.xlsx`: readable review aggregation report
- `out/run_delta.json`: per-source delta between the previous and current run
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
- room, link, or teacher text embedded into the wrong field
- admin or service text embedded into schedule rows
- OCR or PDF garbage
- fragmented PDF slot parsing
- implausible or broken time slots
- missing required fields

Additional guarantees in the current pipeline:

- `week_type` is always filled; if no reliable week marker exists, the default is `Обидва`
- `week_source` is preserved in normalized data
- `autofix_actions` is preserved in normalized data, `manifest.jsonl`, and `review_queue.xlsx`
- orphan metadata-only rows are dropped when they cannot be merged back into a unique timetable slot safely
- `run` cleans the target output directory before writing a new result set
- post-run QA checks every exported workbook automatically

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
- Manual asset seeding improves recoverability, but it does not bypass private or non-public storage restrictions

Current non-parsed KNU statuses:

- `confirmed-blocker`: `Mechmat`, `CSC`, `Military`, `IHT`, `IIR`, `Philology`

Current blocker reasons:

- `Mechmat`: the official source is discoverable, but extracted rows remain too noisy to export reliably
- `CSC`: the official asset is no longer publicly available and now returns `HTTP 410`
- `Military`: the official source is blocked by `HTTP 403 / Cloudflare`
- `IHT`: the official PDF still extracts into rows that are too noisy to export reliably
- `IIR`: official OneDrive-backed assets block anonymous download with `HTTP 403`
- `Philology`: the official PDF still extracts into rows that are too noisy to export reliably

## Development and Tests

Main validation suite:

```powershell
python -m ruff check src tests
python -m mypy src
pytest -q
python -m build
```

Useful commands during development:

```powershell
python -m timetable_scraper doctor
python -m timetable_scraper inspect-source --config config/sources.yaml
python -m timetable_scraper run --config config/sources.yaml
python -m timetable_scraper run --config config/knu_web_schedule.yaml
python -m timetable_scraper run-batched --config config/knu_web_schedule.yaml --batch-size 5
python -m timetable_scraper run-batched --config config/knu_web_smoke.yaml --batch-size 3
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
