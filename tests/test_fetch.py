from __future__ import annotations

import requests

from timetable_scraper.fetch import _fetch_onedrive_resolved, _resolve_content_type, build_http_session, configure_http_session


class StubResponse:
    def __init__(self, *, url: str, status_code: int, headers: dict[str, str] | None = None, text: str = "", content: bytes = b"") -> None:
        self.url = url
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text
        self.content = content

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400


def test_onedrive_resolver_uses_direct_download_candidate(monkeypatch) -> None:
    fallback = StubResponse(
        url="https://onedrive.live.com/redir?resid=RID123&authkey=AUTH456",
        status_code=403,
        headers={"Content-Type": "text/html"},
        text="The request is blocked.",
    )
    downloaded = StubResponse(
        url="https://onedrive.live.com/download?resid=RID123&authkey=AUTH456",
        status_code=200,
        headers={"Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        content=b"xlsx",
    )

    def fake_fetch_remote(url: str, session: requests.Session):
        if "download?resid=RID123&authkey=AUTH456" in url:
            return downloaded
        raise requests.HTTPError("blocked")

    monkeypatch.setattr("timetable_scraper.fetch._fetch_remote", fake_fetch_remote)

    resolved = _fetch_onedrive_resolved("https://1drv.ms/x/test", session=requests.Session(), fallback=fallback)

    assert resolved is downloaded


def test_resolve_content_type_sniffs_pdf_from_octet_stream() -> None:
    response = StubResponse(
        url="https://example.edu/download?id=1",
        status_code=200,
        headers={"Content-Type": "application/octet-stream", "Content-Disposition": 'attachment; filename="schedule.pdf"'},
        content=b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n",
    )

    assert _resolve_content_type(response, response.content, "https://example.edu/file") == "application/pdf"


def test_configure_http_session_sets_retry_adapter_once() -> None:
    session = requests.Session()

    configured = configure_http_session(session)
    configured_again = configure_http_session(configured)

    assert configured is session
    assert configured_again is session
    assert session.headers["User-Agent"] == "Mozilla/5.0"
    assert session.adapters["https://"].max_retries.total == 3
    assert session.adapters["https://"].max_retries.read == 3


def test_build_http_session_returns_configured_session() -> None:
    session = build_http_session()

    assert isinstance(session, requests.Session)
    assert session.headers["User-Agent"] == "Mozilla/5.0"
    assert session.adapters["http://"].max_retries.total == 3
