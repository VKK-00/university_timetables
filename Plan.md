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
