from __future__ import annotations

import argparse
import sys

from .config import load_config
from .doctor import run_doctor
from .pipeline import inspect_config_source, run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="timetable_scraper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the scraper pipeline.")
    run_parser.add_argument("--config", required=True, help="Path to the YAML config.")

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
    if args.command == "run":
        config = load_config(args.config)
        ok, messages = run_doctor(require_tesseract=config.ocr_enabled)
        print("\n".join(messages))
        if not ok:
            return 1
        result = run_pipeline(config)
        print(f"Exported files: {len(result.exported_files)}")
        print(f"Manifest: {result.manifest_path}")
        print(f"Review queue: {result.review_queue_path}")
        if result.source_summary_path:
            print(f"Source summary: {result.source_summary_path}")
        if result.source_report_path:
            print(f"Source report: {result.source_report_path}")
        if result.qa_report_json_path:
            print(f"QA report (json): {result.qa_report_json_path}")
        if result.qa_report_xlsx_path:
            print(f"QA report (xlsx): {result.qa_report_xlsx_path}")
        print(f"Accepted rows: {len(result.rows)}")
        print(f"Review rows: {len(result.review_rows)}")
        print(f"QA warnings: {result.qa_warnings}")
        print(f"QA failures: {result.qa_failures}")
        return 0 if result.qa_failures == 0 else 1
    parser.error(f"Unknown command: {args.command}")
    return 2
