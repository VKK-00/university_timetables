from __future__ import annotations

import argparse
import sys

from .config import load_config, select_sources
from .doctor import run_doctor
from .models import PipelineOutput
from .pipeline import inspect_config_source, run_pipeline, run_pipeline_batched


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="timetable_scraper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the scraper pipeline.")
    run_parser.add_argument("--config", required=True, help="Path to the YAML config.")
    run_parser.add_argument(
        "--sources",
        nargs="*",
        help="Optional source names to run. Accepts space-separated or comma-separated names.",
    )

    batched_parser = subparsers.add_parser("run-batched", help="Run the scraper pipeline in source batches.")
    batched_parser.add_argument("--config", required=True, help="Path to the YAML config.")
    batched_parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Maximum number of sources to process in one batch.",
    )
    batched_parser.add_argument(
        "--sources",
        nargs="*",
        help="Optional source names to run. Accepts space-separated or comma-separated names.",
    )

    doctor_parser = subparsers.add_parser("doctor", help="Check dependencies and OCR stack.")
    doctor_parser.add_argument("--config", required=False, help="Optional config path.")

    inspect_parser = subparsers.add_parser("inspect-source", help="Inspect discovered assets.")
    inspect_parser.add_argument("--config", required=True, help="Path to the YAML config.")
    inspect_parser.add_argument("--source", required=False, help="Optional source name filter.")
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        ok, messages = run_doctor()
        print("\n".join(messages))
        return 0 if ok else 1
    if args.command == "inspect-source":
        config = load_config(args.config)
        print(inspect_config_source(config, source_name=args.source))
        return 0
    if args.command in {"run", "run-batched"}:
        config = select_sources(load_config(args.config), getattr(args, "sources", None))
        ok, messages = run_doctor(require_tesseract=config.ocr_enabled)
        print("\n".join(messages))
        if not ok:
            return 1
        result = (
            run_pipeline_batched(config, batch_size=args.batch_size)
            if args.command == "run-batched"
            else run_pipeline(config)
        )
        _print_run_result(result)
        return 0 if result.qa_failures == 0 else 1
    parser.error(f"Unknown command: {args.command}")
    return 2


def _print_run_result(result: PipelineOutput) -> None:
    print(f"Exported files: {len(result.exported_files)}")
    print(f"Manifest: {result.manifest_path}")
    print(f"Review queue: {result.review_queue_path}")
    if result.source_summary_path:
        print(f"Source summary: {result.source_summary_path}")
    if result.source_report_path:
        print(f"Source report: {result.source_report_path}")
    if result.review_summary_json_path:
        print(f"Review summary (json): {result.review_summary_json_path}")
    if result.review_summary_xlsx_path:
        print(f"Review summary (xlsx): {result.review_summary_xlsx_path}")
    if result.run_delta_path:
        print(f"Run delta: {result.run_delta_path}")
    if result.autofix_report_json_path:
        print(f"Autofix report (json): {result.autofix_report_json_path}")
    if result.autofix_report_xlsx_path:
        print(f"Autofix report (xlsx): {result.autofix_report_xlsx_path}")
    if result.qa_report_json_path:
        print(f"QA report (json): {result.qa_report_json_path}")
    if result.qa_report_xlsx_path:
        print(f"QA report (xlsx): {result.qa_report_xlsx_path}")
    print(f"Accepted rows: {len(result.rows)}")
    print(f"Review rows: {len(result.review_rows)}")
    print(f"Rows with autofixes: {result.autofix_rows}")
    print(f"QA warnings: {result.qa_warnings}")
    print(f"QA failures: {result.qa_failures}")
