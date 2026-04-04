from __future__ import annotations

from .excel import parse_excel_asset
from .html import parse_html_asset
from .pdf import parse_pdf_asset


def parse_asset(fetched_asset, *, ocr_enabled: bool):
    content_type = fetched_asset.content_type.lower()
    locator = fetched_asset.resolved_locator.lower()
    if "spreadsheet" in content_type or locator.endswith((".xlsx", ".xlsm", ".xls", ".csv")):
        return parse_excel_asset(fetched_asset)
    if "pdf" in content_type or locator.endswith(".pdf"):
        return parse_pdf_asset(fetched_asset, ocr_enabled=ocr_enabled)
    if "html" in content_type or locator.endswith((".html", ".htm", ".php", ".aspx")):
        return parse_html_asset(fetched_asset)
    return parse_html_asset(fetched_asset)
