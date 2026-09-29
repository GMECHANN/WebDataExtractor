"""Tests for bounded HTTP behavior, analysis, and pagination orchestration."""

from __future__ import annotations

import pandas as pd
import pytest
from bs4 import BeautifulSoup

import scraper.pagination as pagination_module
import scraper.utils as utils_module
from scraper.analyzer import PageAnalyzer
from scraper.pagination import PaginationConfig, PaginationMode, PaginatedExtractor
from scraper.utils import FetchError, FetchResult


class FakeResponse:
    def __init__(
        self,
        body: bytes = b"",
        *,
        status_code: int = 200,
        content_type: str = "text/html; charset=utf-8",
        location: str | None = None,
    ) -> None:
        self.body = body
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        if location:
            self.headers["Location"] = location
        self.is_redirect = status_code in {301, 302, 303, 307, 308}
        self.is_permanent_redirect = status_code in {301, 308}
        self.closed = False

    def iter_content(self, chunk_size: int):
        yield from (self.body[index : index + chunk_size] for index in range(0, len(self.body), chunk_size))

    def close(self) -> None:
        self.closed = True


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = iter(responses)
        self.headers: dict[str, str] = {}
        self.requested_urls: list[str] = []

    def get(self, url: str, **_: object) -> FakeResponse:
        self.requested_urls.append(url)
        return next(self.responses)


def test_fetch_html_decodes_unicode_and_follows_validated_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(
        [
            FakeResponse(status_code=302, location="/catalog"),
            FakeResponse("<title>Catálogo Perú</title>".encode("utf-8")),
        ]
    )
    validated: list[str] = []

    def validation(url: str, *, resolve_dns: bool = False) -> str:
        validated.append(url)
        return url

    monkeypatch.setattr(utils_module, "validate_url", validation)
    monkeypatch.setattr(utils_module.requests, "Session", lambda: session)

    result = utils_module.fetch_html("https://example.com/start")

    assert result.url == "https://example.com/catalog"
    assert "Catálogo Perú" in result.html
    assert validated == ["https://example.com/start", "https://example.com/catalog"]


@pytest.mark.parametrize("status", [403, 404, 429, 503])
def test_fetch_html_reports_common_http_errors(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    monkeypatch.setattr(utils_module, "validate_url", lambda url, resolve_dns=False: url)
    monkeypatch.setattr(utils_module.requests, "Session", lambda: FakeSession([FakeResponse(status_code=status)]))

    with pytest.raises(FetchError, match=str(status)):
        utils_module.fetch_html("https://example.com/problem")


def test_analyzer_finds_tables_and_repeated_elements() -> None:
    html = """
    <title>Results</title>
    <table><tr><th>Name</th></tr><tr><td>A</td></tr></table>
    <div class="result">A</div><div class="result">B</div><div class="result">C</div>
    """
    result = PageAnalyzer().analyze_html(html)

    assert result.title == "Results"
    assert len(result.table_summaries) == 1
    assert any(group.selector == "div.result" and group.count == 3 for group in result.repeated_groups)


def test_analyzer_escapes_special_css_class_names() -> None:
    html = '<ul class="md:list"><li>A</li><li>B</li></ul>'
    result = PageAnalyzer().analyze_html(html)

    selector = result.repeated_groups[0].selector
    assert selector == r"ul.md\:list > li"
    assert len(BeautifulSoup(html, "lxml").select(selector)) == 2


def test_url_pattern_pagination_is_bounded_and_combines_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    first = FetchResult("https://example.com/items?page=1", 200, "page one", "text/html")
    fetched_urls: list[str] = []

    def fake_fetch(url: str, *, timeout: int) -> FetchResult:
        fetched_urls.append(url)
        return FetchResult(url, 200, f"page {len(fetched_urls) + 1}", "text/html")

    monkeypatch.setattr(pagination_module, "fetch_html", fake_fetch)
    monkeypatch.setattr(pagination_module, "validate_url", lambda url: url)
    monkeypatch.setattr(pagination_module.time, "sleep", lambda _: None)

    result = PaginatedExtractor().run(
        first,
        lambda html, _: pd.DataFrame({"content": [html]}),
        PaginationConfig(
            mode=PaginationMode.URL_PATTERN,
            maximum_pages=3,
            delay_seconds=0.5,
            url_pattern="https://example.com/items?page={page}",
        ),
    )

    assert result.pages_processed == 3
    assert result.dataframe["content"].tolist() == ["page one", "page 2", "page 3"]
    assert fetched_urls == ["https://example.com/items?page=2", "https://example.com/items?page=3"]


def test_next_selector_pagination_follows_relative_links(monkeypatch: pytest.MonkeyPatch) -> None:
    pages = {
        "https://example.com/page-2.html": '<p>page two</p><a class="next" href="page-3.html">Next</a>',
        "https://example.com/page-3.html": "<p>page three</p>",
    }
    first = FetchResult(
        "https://example.com/index.html",
        200,
        '<p>page one</p><a class="next" href="page-2.html">Next</a>',
        "text/html",
    )
    fetched_urls: list[str] = []

    def fake_fetch(url: str, *, timeout: int) -> FetchResult:
        fetched_urls.append(url)
        return FetchResult(url, 200, pages[url], "text/html")

    monkeypatch.setattr(pagination_module, "fetch_html", fake_fetch)
    monkeypatch.setattr(pagination_module, "validate_url", lambda url: url)
    monkeypatch.setattr(pagination_module.time, "sleep", lambda _: None)

    result = PaginatedExtractor().run(
        first,
        lambda html, _: pd.DataFrame({"content": [BeautifulSoup(html, "lxml").p.get_text()]}),
        PaginationConfig(
            mode=PaginationMode.NEXT_SELECTOR,
            maximum_pages=3,
            delay_seconds=1.0,
            next_selector="li.next a, a.next",
        ),
    )

    assert result.pages_processed == 3
    assert result.dataframe["content"].tolist() == ["page one", "page two", "page three"]
    assert fetched_urls == ["https://example.com/page-2.html", "https://example.com/page-3.html"]
