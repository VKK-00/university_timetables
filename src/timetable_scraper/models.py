from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SourceConfig:
    kind: str
    name: str
    path: Path | None = None
    url: str | None = None
    recurse: bool = True
    allow_domains: list[str] = field(default_factory=list)
    schedule_keywords: list[str] = field(default_factory=list)
    follow_links_depth: int = 0
    manual_assets: list["ManualAssetSeed"] = field(default_factory=list)


@dataclass(slots=True)
class ManualAssetSeed:
    url: str
    display_name: str = ""
    asset_kind: str = "file_url"


@dataclass(slots=True)
class AppConfig:
    template_path: Path
    output_dir: Path
    cache_dir: Path
    confidence_threshold: float
    ocr_enabled: bool
    sources: list[SourceConfig]
    manual_assets_path: Path | None = None


@dataclass(slots=True)
class DiscoveredAsset:
    source_name: str
    source_kind: str
    asset_kind: str
    locator: str
    display_name: str
    source_root_url: str = ""
    source_url_or_path: str = ""
    origin_kind: str = "official_page"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_root_url:
            self.source_root_url = self.source_url_or_path or self.locator
        if not self.source_url_or_path:
            self.source_url_or_path = self.source_root_url


@dataclass(slots=True)
class DiscoveryIssue:
    source_name: str
    reason: str
    locator: str | None = None


@dataclass(slots=True)
class DiscoveryResult:
    assets: list[DiscoveredAsset]
    issues: list[DiscoveryIssue]


@dataclass(slots=True)
class FetchedAsset:
    asset: DiscoveredAsset
    content: bytes
    content_type: str
    content_hash: str
    resolved_locator: str


@dataclass(slots=True)
class RawRecord:
    values: dict[str, Any]
    row_index: int
    sheet_name: str
    raw_excerpt: str
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ParsedSheet:
    sheet_name: str
    program: str
    faculty: str
    records: list[RawRecord]
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ParsedDocument:
    asset: FetchedAsset
    sheets: list[ParsedSheet]
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class NormalizedRow:
    program: str
    faculty: str
    week_type: str
    day: str
    start_time: str
    end_time: str
    subject: str
    teacher: str = ""
    lesson_type: str = ""
    link: str = ""
    room: str = ""
    groups: str = ""
    course: str = ""
    notes: str = ""
    week_source: str = "default"
    sheet_name: str = ""
    source_name: str = ""
    source_kind: str = ""
    source_root_url: str = ""
    asset_locator: str = ""
    source_url_or_path: str = ""
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)
    autofix_actions: list[str] = field(default_factory=list)
    qa_flags: list[str] = field(default_factory=list)
    qa_severity: str = "none"
    raw_excerpt: str = ""
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.source_root_url:
            self.source_root_url = self.source_url_or_path
        if not self.source_url_or_path:
            self.source_url_or_path = self.source_root_url
        if not self.asset_locator:
            self.asset_locator = self.source_root_url


@dataclass(slots=True)
class SourceRunSummary:
    source_name: str
    source_root_url: str
    status: str
    accepted_rows: int = 0
    review_rows: int = 0
    autofix_rows: int = 0
    discovered_assets: int = 0
    attempted_assets: int = 0
    discovery_issues: list[str] = field(default_factory=list)
    runtime_issues: list[str] = field(default_factory=list)
    top_review_warnings: list[str] = field(default_factory=list)
    top_review_qa_flags: list[str] = field(default_factory=list)
    note: str = ""


@dataclass(slots=True)
class WorkbookQaSheetSummary:
    sheet_name: str
    row_count: int
    issue_count: int
    issues: list[str] = field(default_factory=list)


@dataclass(slots=True)
class WorkbookQaSummary:
    file_path: Path
    status: str
    row_count: int
    issue_count: int
    issues: list[str] = field(default_factory=list)
    sheets: list[WorkbookQaSheetSummary] = field(default_factory=list)


@dataclass(slots=True)
class PipelineOutput:
    exported_files: list[Path]
    manifest_path: Path
    review_queue_path: Path
    rows: list[NormalizedRow]
    review_rows: list[NormalizedRow]
    source_summary_path: Path | None = None
    source_report_path: Path | None = None
    review_summary_json_path: Path | None = None
    review_summary_xlsx_path: Path | None = None
    run_delta_path: Path | None = None
    autofix_report_json_path: Path | None = None
    autofix_report_xlsx_path: Path | None = None
    autofix_rows: int = 0
    qa_report_json_path: Path | None = None
    qa_report_xlsx_path: Path | None = None
    qa_failures: int = 0
    qa_warnings: int = 0
    workbook_qa: list[WorkbookQaSummary] = field(default_factory=list)
    source_summaries: list[SourceRunSummary] = field(default_factory=list)
