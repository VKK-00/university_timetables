# KNU Web Run — 2026-04-05

Config: `config/knu_web_schedule.yaml`

Run output:
- Exported files: `185`
- Accepted rows: `46080`
- Review rows: `954`
- Manifest: `out_knu_web/manifest.jsonl`
- Review queue: `out_knu_web/review_queue.xlsx`
- Source summary: `out_knu_web/source_summary.json`
- Source report: `out_knu_web/source_summary.md`

Key implementation changes behind this run:
- Added stable provenance fields: `source_root_url`, `asset_locator`, `source_name`, `origin_kind`.
- Normalized manifest and export grouping to use official source provenance instead of nested storage URLs or Google doc ids.
- Added Google Drive folder expansion with root-source attribution.
- Added Dropfiles/Joomla discovery for philosophy-style schedule pages.
- Added OneDrive resolver with explicit blocker failure when public download is blocked.
- Hardened HTML parsing so link-index pages no longer create fake zero-row schedule sheets.
- Hardened PDF parsing so incomplete fragments are rejected instead of leaking into ambiguous review-only rows.
- Added per-source summary generation with final statuses: `parsed`, `review-only`, `confirmed-blocker`.

Final source statuses:

Parsed:
- `https://geo.knu.ua/navchannya/rozklad-zanyat/` — `30` accepted, `0` review
- `https://econom.knu.ua/for_students/schedule/rozklad/` — `1610` accepted, `0` review
- `https://history.univ.kiev.ua/studentam/schedule/` — `727` accepted, `0` review
- `https://mechmat.knu.ua/golovna/studentu/rozklad/` — `8` accepted, `0` review
- `https://fit.knu.ua/for-students/lessons-schedule` — `26928` accepted, `954` review
- `https://psy.knu.ua/study/schedule` — `99` accepted, `0` review
- `https://sociology.knu.ua/uk/students` — `4107` accepted, `0` review
- `https://phys.knu.ua/navchannya/rozklad-zanyat?ad` — `10602` accepted, `0` review
- `https://chem.knu.ua/ua/teaching_resources/teaching_schedule/` — `543` accepted, `0` review
- `http://www.geol.univ.kiev.ua/rozklad/rozklad_II_sem_2025_2026.xlsx` — `115` accepted, `0` review
- `https://biomed.knu.ua/students-postgraduates/general-information/rozklad-zaniat.html` — `1311` accepted, `0` review

Review-only:
- none

Confirmed blockers:
- `https://csc.knu.ua/uk/schedule/` — official source returns `HTTP 500`
- `https://rex.knu.ua/for-students/class-times/` — assets discovered, but current parsers do not reconstruct complete rows from published PDFs
- `https://www.philosophy.knu.ua/study/educational-process` — Dropfiles assets discovered, but published PDFs still do not yield complete rows
- `https://law.knu.ua/schedule/` — published PDFs were discovered, but complete weekday-based schedule rows are not recoverable from the current PDF layout
- `https://mil.knu.ua` — redirect ends on `HTTP 403 / Cloudflare`
- `https://iht.knu.ua/wp-content/uploads/2026/02/RozkladННІВТ-2-25-26.pdf` — published PDF was discovered, but complete weekday-based schedule rows are not recoverable from the current PDF layout
- `https://www.iir.edu.ua/rozklad` — OneDrive public downloads are blocked with `HTTP 403`
- `https://journ.knu.ua/rozklad-zaniat/` — published asset discovered, but workbook layout still yields no complete normalized rows
- `https://philology.knu.ua/nauka/aspirantura/rozklad-zanyat/` — published Google Drive assets discovered, but no complete rows were parsed

Notable correctness improvements confirmed by this run:
- History rows are now attributed to the official history schedule page instead of individual Google Drive folder URLs.
- Law and IHT are no longer left in ambiguous `review-only`; both now land in deterministic `confirmed-blocker` states instead of leaking garbage rows into parsed output.
- Philosophy is no longer a discovery blind spot; Dropfiles categories and file links are extracted from the official page.
- IIR failures are now explicit OneDrive blockers instead of silent zero-row outcomes.
