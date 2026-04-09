# Plan

## Milestone 1 - Baseline and gap analysis
- [x] Inspect the current automated QA and normalization pipeline
- [x] Identify missing automation visibility and documentation gaps

## Milestone 2 - Autofix trace and reporting
- [x] Add per-row `autofix_actions` to normalized data
- [x] Persist autofix metadata to `manifest.jsonl` and `review_queue.xlsx`
- [x] Generate `autofix_report.json` and `autofix_report.xlsx`
- [x] Surface autofix report paths and counts in CLI output

## Milestone 3 - Validation and docs
- [x] Update `README.md` to describe automated checks and autofixes accurately
- [x] Run `ruff check`
- [x] Run `mypy`
- [x] Run `pytest`
- [x] Run `python -m build`

## Milestone 4 - Repo-wide typecheck hardening and release
- [x] Make repo-wide `python -m mypy src` pass
- [x] Re-run `ruff check`
- [x] Re-run `pytest`
- [x] Re-run `python -m build`
- [x] Re-run production `doctor` and `run`
- [x] Commit and push only relevant changes

## Milestone 5 - Review triage and acceptance dashboards
- [x] Add `review_summary.json` and `review_summary.xlsx` with source-level review aggregation
- [x] Add `run_delta.json` with per-source deltas between consecutive runs
- [x] Surface new report paths in CLI output
- [x] Validate with `ruff check`
- [x] Validate with `mypy`
- [x] Validate with `pytest`
- [x] Validate with `python -m build`

## Milestone 6 - Manual asset seeding for blocked sources
- [x] Extend config to support optional `manual_assets.yaml`
- [x] Inject manual direct assets into discovery with provenance preserved
- [x] Document the manual direct-file fallback flow
- [x] Validate with `ruff check`
- [x] Validate with `mypy`
- [x] Validate with `pytest`
- [x] Validate with `python -m build`

## Milestone 7 - Review backlog reduction for Physics and FIT
- [x] Reduce Physics review rows without relaxing global QA
- [x] Reduce FIT review rows by filtering non-schedule assets and improving parsing
- [x] Resolve `Philology` from `review-only` to `parsed` or `confirmed-blocker`
- [x] Re-run production `doctor`
- [x] Re-run production `run`
- [x] Validate with `ruff check`
- [x] Validate with `mypy`
- [x] Validate with `pytest`
- [x] Validate with `python -m build`

## Milestone 8 - Final docs sync
- [x] Update `README.md` with the new reports, manual asset flow, and latest run metrics
- [x] Verify docs match the latest source summary and QA outputs
- [x] Final `ruff check`
- [x] Final `mypy`
- [x] Final `pytest`
- [x] Final `python -m build`

## Milestone 9 - Final source polish
- [x] Add official direct manual assets for remaining recoverable blocker sources
- [x] Reduce false-positive review rows for Physics without relaxing core QA
- [x] Reduce FIT meeting-code and room-fragment noise without hiding ambiguous data
- [x] Re-run `ruff check`
- [x] Re-run `mypy`
- [x] Re-run `pytest`
- [x] Re-run `python -m build`
- [x] Re-run production `doctor`
- [x] Re-run production `run`
- [x] Sync `README.md` to the latest run if metrics change

## Milestone 10 - REX and Journalism backlog reduction
- [x] Reduce `rex-schedule` PDF false positives caused by dotted lecture markers and slash-heavy wrapped subjects
- [x] Infer stable end times for Journalism grid rows that currently export `start == end`
- [x] Re-run `ruff check`
- [x] Re-run `mypy`
- [x] Re-run `pytest`
- [x] Re-run `python -m build`
- [x] Re-run targeted production `run`
- [x] Sync `README.md` if the top-line metrics change materially

## Milestone 11 - Full KNU rerun and docs sync
- [x] Re-run full production `run` for `config/knu_web_schedule.yaml`
- [x] Stabilize `fit-schedule` in full KNU config with official direct sheet assets
- [x] Re-run full production `run` after the FIT source fix
- [x] Update `README.md` if the full-run metrics change materially
- [x] Re-run `ruff check`
- [x] Re-run `mypy`
- [x] Re-run `pytest`
- [x] Re-run `python -m build`

## Milestone 12 - Early service-row and report noise reduction
- [x] Filter obvious non-schedule report assets earlier in discovery
- [x] Drop service-only timetable rows such as self-study-day and elective headers before QA
- [x] Add regression tests for URL-only report filtering and non-schedule row dropping
- [x] Re-run `ruff check`
- [x] Re-run `mypy`
- [x] Re-run `pytest`
- [x] Re-run `python -m build`
- [x] Re-run full production `run`
- [x] Update `README.md` if the full-run metrics change materially

## Milestone 13 - Time-slot repair and non-class row cleanup
- [x] Repair short or reversed single-slot times before QA when the row otherwise looks like a real class
- [x] Drop non-class rows even when only `groups` / `course` context remains
- [x] Add regression tests for implausible time repair and grouped service-row dropping
- [x] Re-run `ruff check`
- [x] Re-run `mypy`
- [x] Re-run `pytest`
- [x] Re-run `python -m build`
- [x] Re-run full production `run`
- [x] Update `README.md` if the full-run metrics change materially

## Milestone 14 - PDF continuation line repair
- [x] Recognize `teacher + room` and `teacher + room + link` continuation lines in PDF grid tables before they become fake subjects
- [x] Add regression tests for teacher-room-only PDF lines and multiline PDF continuation records
- [x] Re-run `ruff check`
- [x] Re-run `mypy`
- [x] Re-run `pytest`
- [x] Re-run `python -m build`
- [x] Re-run full production `run`
- [x] Update `README.md` if the full-run metrics change materially

## Milestone 15 - PDF subject-noise cleanup
- [x] Strip fragmented URL tails and date-time fragments out of PDF-derived `subject` fields before QA
- [x] Add regression tests for subject cleanup with split link/date fragments
- [x] Re-run `ruff check`
- [x] Re-run `mypy`
- [x] Re-run `pytest`
- [x] Re-run `python -m build`
- [x] Re-run full production `run`
- [x] Update `README.md` if the full-run metrics change materially

## Milestone 16 - Long-practice QA allowance
- [x] Allow long but plausible practice blocks in QA without dropping the existing hard-fail checks for broken times
- [x] Add regression tests for long practice durations and still-failing long non-practice durations
- [x] Re-run `ruff check`
- [x] Re-run `mypy`
- [x] Re-run `pytest`
- [x] Re-run `python -m build`
- [x] Re-run full production `run`
- [x] Update `README.md` if the full-run metrics change materially

## Milestone 17 - Leading-teacher subject repair
- [x] Move leading teacher-like prefixes out of PDF-derived `subject` fields before wrapped-subject collapse
- [x] Add regression tests for REX-style `teacher / subject / continuation` rows without relaxing unrelated subject QA
- [x] Re-run `ruff check`
- [x] Re-run `mypy`
- [x] Re-run `pytest`
- [x] Re-run `python -m build`
- [x] Re-run full production `run`
- [x] Update `README.md` if the full-run metrics change materially

## Milestone 18 - Teacher-list normalization
- [x] Normalize broken multi-teacher lists so law-style lecture streams do not fail QA only because titles and names were split apart
- [x] Add regression tests for title-plus-name chains and compact surnames with initials
- [x] Re-run `ruff check`
- [x] Re-run `mypy`
- [x] Re-run `pytest`
- [x] Re-run `python -m build`
- [x] Re-run full production `run`
- [x] Update `README.md` if the full-run metrics change materially

## Milestone 19 - Metadata-only slot merge
- [x] Merge metadata-only normalized rows into a single matching subject row for the same slot when the match is unambiguous
- [x] Add regression tests for law-style `teacher/room only` continuation rows and keep ambiguous multi-subject slots untouched
- [x] Re-run `ruff check`
- [x] Re-run `mypy`
- [x] Re-run `pytest`
- [x] Re-run `python -m build`
- [x] Re-run full production `run`
- [x] Update `README.md` if the full-run metrics change materially
