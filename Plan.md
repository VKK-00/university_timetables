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
