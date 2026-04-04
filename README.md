# university_timetables

Universal KNU-first scraper for university schedules. It reads local folders and ZIP archives, direct files, public Google Sheets/Drive links, faculty web pages, HTML tables, and PDF files with OCR fallback, then exports normalized Excel files in the same layout as [Шаблон.xlsx](./Шаблон.xlsx).

## Install

```powershell
pip install -e .[dev]
```

The OCR pipeline expects Tesseract with `eng` and `ukr` language data. You can verify the stack with:

```powershell
python -m timetable_scraper doctor
```

## Main Run

```powershell
python -m timetable_scraper run --config config/sources.yaml
```

The default config points to the provided KNU archive and writes results to `out/`.

## Config Format

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

Supported `sources[].kind` values:

- `folder`
- `zip`
- `web_page`
- `file_url`
- `google_sheet`

## CLI

```powershell
python -m timetable_scraper doctor
python -m timetable_scraper inspect-source --config config/sources.yaml
python -m timetable_scraper run --config config/sources.yaml
```

## Outputs

- `out/<faculty>/<program>.xlsx`: normalized schedule workbooks built from the template.
- `out/manifest.jsonl`: one JSON line per parsed row with provenance, confidence, warnings, and content hash.
- `out/review_queue.xlsx`: low-confidence or incomplete rows that need manual review.

## Test Suite

```powershell
pytest
```

The test set includes:

- 6 real workbook fixtures extracted from the provided KNU archive
- HTML discovery and table parsing fixtures
- text PDF parsing
- scanned PDF OCR parsing
- full end-to-end processing of the provided ZIP archive
