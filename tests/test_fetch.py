from __future__ import annotations

import requests

from timetable_scraper.fetch import _fetch_onedrive_resolved


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
