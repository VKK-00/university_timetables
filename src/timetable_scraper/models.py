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


@dataclass(slots=True)
class AppConfig:
    template_path: Path
    output_dir: Path
    cache_dir: Path
    confidence_threshold: float
    ocr_enabled: bool
    sources: list[SourceConfig]


@dataclass(slots=True)
class DiscoveredAsset:
    source_name: str
    source_kind: str
    source_url_or_path: str
    asset_kind: str
    locator: str
    display_name: str
    metadata: dict[str, Any] = field(default_factory=dict)


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
    sheet_name: str = ""
    source_kind: str = ""
    source_url_or_path: str = ""
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)
    raw_excerpt: str = ""
    content_hash: str = ""


@dataclass(slots=True)
class PipelineOutput:
    exported_files: list[Path]
    manifest_path: Path
    review_queue_path: Path
    rows: list[NormalizedRow]
    review_rows: list[NormalizedRow]
