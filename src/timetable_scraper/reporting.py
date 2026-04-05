from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from .models import DiscoveryResult, NormalizedRow, SourceConfig, SourceRunSummary
from .utils import ensure_parent, humanize_source_name, json_dumps


def build_source_summaries(
    sources: list[SourceConfig],
    discovery: DiscoveryResult,
    accepted_rows: list[NormalizedRow],
    review_rows: list[NormalizedRow],
    *,
    attempted_assets: Counter[str],
    runtime_issues: dict[str, list[str]],
) -> list[SourceRunSummary]:
    discovered_assets = Counter(asset.source_name for asset in discovery.assets)
    discovery_issues: dict[str, list[str]] = defaultdict(list)
    for issue in discovery.issues:
        discovery_issues[issue.source_name].append(issue.reason if not issue.locator else f"{issue.reason} [{issue.locator}]")

    accepted_counts = Counter(row.source_name for row in accepted_rows)
    review_counts = Counter(row.source_name for row in review_rows)
    review_warning_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in review_rows:
        for warning in row.warnings:
            review_warning_counts[row.source_name][warning] += 1

    summaries: list[SourceRunSummary] = []
    for source in sources:
        source_root_url = source.url or (str(source.path.resolve()) if source.path is not None else "")
        top_review_warnings = [warning for warning, _ in review_warning_counts[source.name].most_common(5)]
        status, note = _classify_source(
            accepted_rows=accepted_counts[source.name],
            review_rows=review_counts[source.name],
            discovered_assets=discovered_assets[source.name],
            discovery_issues=discovery_issues[source.name],
            runtime_issues=runtime_issues.get(source.name, []),
            top_review_warnings=top_review_warnings,
        )
        summaries.append(
            SourceRunSummary(
                source_name=source.name,
                source_root_url=source_root_url,
                status=status,
                accepted_rows=accepted_counts[source.name],
                review_rows=review_counts[source.name],
                discovered_assets=discovered_assets[source.name],
                attempted_assets=attempted_assets[source.name],
                discovery_issues=discovery_issues[source.name],
                runtime_issues=runtime_issues.get(source.name, []),
                top_review_warnings=top_review_warnings,
                note=note,
            )
        )
    return summaries


def write_source_summaries(summaries: list[SourceRunSummary], *, output_dir: Path) -> tuple[Path, Path]:
    json_path = output_dir / "source_summary.json"
    report_path = output_dir / "source_summary.md"
    ensure_parent(json_path)
    json_path.write_text(
        "[\n"
        + ",\n".join(
            json_dumps(
                {
                    "source_name": summary.source_name,
                    "source_root_url": summary.source_root_url,
                    "status": summary.status,
                    "accepted_rows": summary.accepted_rows,
                    "review_rows": summary.review_rows,
                    "discovered_assets": summary.discovered_assets,
                    "attempted_assets": summary.attempted_assets,
                    "discovery_issues": summary.discovery_issues,
                    "runtime_issues": summary.runtime_issues,
                    "top_review_warnings": summary.top_review_warnings,
                    "note": summary.note,
                }
            )
            for summary in summaries
        )
        + "\n]\n",
        encoding="utf-8",
    )
    report_path.write_text(_render_summary_markdown(summaries), encoding="utf-8")
    return json_path, report_path


def _classify_source(
    *,
    accepted_rows: int,
    review_rows: int,
    discovered_assets: int,
    discovery_issues: list[str],
    runtime_issues: list[str],
    top_review_warnings: list[str],
) -> tuple[str, str]:
    blocker_reason = _find_blocker_reason([*runtime_issues, *discovery_issues])
    if accepted_rows > 0:
        if review_rows > 0:
            return "parsed", f"{review_rows} review rows remain"
        return "parsed", ""
    if blocker_reason:
        return "confirmed-blocker", blocker_reason
    if review_rows > 0:
        if {"missing_day", "missing_subject"} & set(top_review_warnings):
            return "review-only", "Rows were extracted but key schedule fields are incomplete"
        return "review-only", ", ".join(top_review_warnings[:3])
    if discovered_assets > 0:
        return "confirmed-blocker", "Assets were discovered but parsers did not yield complete schedule rows"
    return "confirmed-blocker", "No public schedule assets discovered from the official source"


def _find_blocker_reason(reasons: list[str]) -> str:
    for reason in reasons:
        lowered = reason.casefold()
        if "http 500" in lowered or "500 internal server error" in lowered or "500 server error" in lowered:
            return "Official source returns HTTP 500"
        if "http 403" in lowered or "403 client error" in lowered or "blocked" in lowered or "cloudflare" in lowered:
            return "Access to the official source is blocked (HTTP 403 / Cloudflare)"
        if "onedrive public download blocked" in lowered:
            return "OneDrive public download is blocked"
    return ""


def _render_summary_markdown(summaries: list[SourceRunSummary]) -> str:
    lines = ["# Source Summary", ""]
    for status in ("parsed", "review-only", "confirmed-blocker"):
        lines.append(f"## {status}")
        subset = [summary for summary in summaries if summary.status == status]
        if not subset:
            lines.append("- none")
            lines.append("")
            continue
        for summary in subset:
            label = humanize_source_name(summary.source_name) or summary.source_name
            detail = f"accepted={summary.accepted_rows}, review={summary.review_rows}, assets={summary.discovered_assets}"
            suffix = f" — {summary.note}" if summary.note else ""
            lines.append(f"- {label} — {detail} — {summary.source_root_url}{suffix}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
