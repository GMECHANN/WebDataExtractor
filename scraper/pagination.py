"""Conservative, bounded pagination for extraction jobs."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup
from soupsieve import SelectorSyntaxError

from .utils import FetchResult, WebDataExtractorError, fetch_html, validate_url


class PaginationMode(str, Enum):
    NONE = "No pagination"
    NEXT_SELECTOR = "Next button CSS selector"
    URL_PATTERN = "URL pattern"


@dataclass(frozen=True)
class PaginationConfig:
    mode: PaginationMode = PaginationMode.NONE
    maximum_pages: int = 5
    delay_seconds: float = 1.0
    next_selector: str = ""
    url_pattern: str = ""


@dataclass(frozen=True)
class PaginationResult:
    dataframe: pd.DataFrame
    pages_processed: int
    visited_urls: list[str]


class PaginatedExtractor:
    """Apply an extraction function over a small number of public pages."""

    def run(
        self,
        first_page: FetchResult,
        extraction: Callable[[str, str], pd.DataFrame],
        config: PaginationConfig,
        *,
        timeout: int = 12,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> PaginationResult:
        maximum = max(1, min(int(config.maximum_pages), 20))
        delay = max(0.5, min(float(config.delay_seconds), 10.0))
        current = first_page
        frames: list[pd.DataFrame] = []
        visited: list[str] = []

        for page_number in range(1, maximum + 1):
            if current.url in visited:
                break
            visited.append(current.url)
            frame = extraction(current.html, current.url)
            if not frame.empty:
                frames.append(frame)
            if progress_callback:
                progress_callback(page_number, maximum)

            next_url = self._next_url(current, config, page_number)
            if not next_url or page_number >= maximum:
                break
            next_url = validate_url(next_url)
            if next_url in visited:
                break
            time.sleep(delay)
            current = fetch_html(next_url, timeout=timeout)

        combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        return PaginationResult(combined, len(visited), visited)

    def _next_url(self, page: FetchResult, config: PaginationConfig, page_number: int) -> str | None:
        if config.mode == PaginationMode.NONE:
            return None
        if config.mode == PaginationMode.URL_PATTERN:
            if "{page}" not in config.url_pattern:
                raise WebDataExtractorError('The URL pattern must contain the "{page}" placeholder.')
            try:
                return config.url_pattern.format(page=page_number + 1)
            except (KeyError, ValueError) as exc:
                raise WebDataExtractorError("The URL pattern is invalid.") from exc

        if not config.next_selector.strip():
            raise WebDataExtractorError("Enter a CSS selector for the next-page link.")
        soup = BeautifulSoup(page.html, "lxml")
        try:
            element = soup.select_one(config.next_selector)
        except SelectorSyntaxError as exc:
            raise WebDataExtractorError("The next-button CSS selector is invalid.") from exc
        if element is None:
            return None
        href = element.get("href")
        return urljoin(page.url, href) if href else None
