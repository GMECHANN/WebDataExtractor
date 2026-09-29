"""Shared validation, HTTP, and data-cleaning utilities."""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import UnicodeDammit

USER_AGENT = "WebDataExtractor/1.0 (+portfolio project; respectful public-web client)"
DEFAULT_TIMEOUT = 12
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 5


class WebDataExtractorError(Exception):
    """Base exception containing a message suitable for the UI."""


class InvalidURLError(WebDataExtractorError):
    """Raised when a URL is malformed or targets a non-public address."""


class FetchError(WebDataExtractorError):
    """Raised when an HTTP page cannot be retrieved safely."""


@dataclass(frozen=True)
class FetchResult:
    """A successfully fetched HTML document."""

    url: str
    status_code: int
    html: str
    content_type: str


def clean_text(value: object) -> str:
    """Collapse whitespace and return a predictable string value."""

    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_column_name(name: object) -> str:
    """Convert a column label to lowercase snake_case."""

    normalized = clean_text(name).lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    return normalized or "column"


def _resolved_addresses(hostname: str) -> Iterable[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        records = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise InvalidURLError("The website hostname could not be resolved.") from exc

    seen: set[str] = set()
    for record in records:
        address = record[4][0]
        if address not in seen:
            seen.add(address)
            yield ipaddress.ip_address(address)


def _is_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return address.is_global


def validate_url(url: str, *, resolve_dns: bool = False) -> str:
    """Validate an HTTP(S) URL and optionally reject non-public DNS targets.

    DNS resolution is optional so syntax validation remains deterministic in tests
    and while typing. Network requests always enable it.
    """

    candidate = clean_text(url)
    if not candidate:
        raise InvalidURLError("Enter a website URL before continuing.")

    try:
        parsed = urlparse(candidate)
        port = parsed.port
    except ValueError as exc:
        raise InvalidURLError("The URL contains an invalid port or address.") from exc

    if parsed.scheme.lower() not in {"http", "https"}:
        raise InvalidURLError("Only http:// and https:// URLs are supported.")
    if not parsed.hostname:
        raise InvalidURLError("The URL must include a valid hostname.")
    if parsed.username or parsed.password:
        raise InvalidURLError("URLs containing credentials are not supported.")
    if port is not None and not 1 <= port <= 65535:
        raise InvalidURLError("The URL contains an invalid port.")

    hostname = parsed.hostname.rstrip(".")
    if hostname.lower() == "localhost" or hostname.lower().endswith(".localhost"):
        raise InvalidURLError("Local and private network addresses are not allowed.")

    try:
        literal_address = ipaddress.ip_address(hostname)
    except ValueError:
        literal_address = None
    if literal_address is not None and not _is_public_address(literal_address):
        raise InvalidURLError("Local and private network addresses are not allowed.")

    if resolve_dns:
        addresses = list(_resolved_addresses(hostname))
        if not addresses or any(not _is_public_address(item) for item in addresses):
            raise InvalidURLError("The hostname resolves to a non-public network address.")

    return candidate


def friendly_http_error(status_code: int) -> str:
    """Return a non-technical explanation for a failed HTTP status."""

    messages = {
        403: "The website denied access (HTTP 403). Respect its access policy and try another public page.",
        404: "The requested page was not found (HTTP 404). Check the URL.",
        429: "The website is rate-limiting requests (HTTP 429). Wait before trying again.",
    }
    if status_code in messages:
        return messages[status_code]
    if status_code >= 500:
        return f"The website returned a server error (HTTP {status_code}). Try again later."
    return f"The website returned HTTP {status_code} and the page could not be processed."


def fetch_html(url: str, *, timeout: int = DEFAULT_TIMEOUT) -> FetchResult:
    """Fetch a bounded public HTML page, validating every redirect target."""

    current_url = validate_url(url, resolve_dns=True)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
        }
    )

    for _ in range(MAX_REDIRECTS + 1):
        try:
            response = session.get(
                current_url,
                timeout=timeout,
                allow_redirects=False,
                stream=True,
            )
        except requests.Timeout as exc:
            raise FetchError(f"The website did not respond within {timeout} seconds.") from exc
        except requests.ConnectionError as exc:
            raise FetchError("A connection to the website could not be established.") from exc
        except requests.RequestException as exc:
            raise FetchError("The website request failed. Check the URL and try again.") from exc

        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise FetchError("The website returned an invalid redirect.")
            current_url = validate_url(urljoin(current_url, location), resolve_dns=True)
            continue

        if response.status_code >= 400:
            response.close()
            raise FetchError(friendly_http_error(response.status_code))

        content_type = response.headers.get("Content-Type", "").lower()
        if "html" not in content_type and "xhtml" not in content_type:
            response.close()
            raise FetchError("The URL did not return an HTML page.")

        content_length = response.headers.get("Content-Length")
        if content_length and content_length.isdigit() and int(content_length) > MAX_RESPONSE_BYTES:
            response.close()
            raise FetchError("The page is larger than the 5 MB safety limit.")

        chunks: list[bytes] = []
        total = 0
        try:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                total += len(chunk)
                if total > MAX_RESPONSE_BYTES:
                    raise FetchError("The page is larger than the 5 MB safety limit.")
                chunks.append(chunk)
        finally:
            response.close()

        raw = b"".join(chunks)
        charset_match = re.search(r"charset\s*=\s*['\"]?([^;'\"\s]+)", content_type)
        declared_encodings = [charset_match.group(1)] if charset_match else []
        decoded = UnicodeDammit(
            raw,
            known_definite_encodings=declared_encodings,
            is_html=True,
        ).unicode_markup
        return FetchResult(
            url=current_url,
            status_code=response.status_code,
            html=decoded if decoded is not None else raw.decode("utf-8", errors="replace"),
            content_type=content_type,
        )

    raise FetchError(f"The website redirected more than {MAX_REDIRECTS} times.")


def clean_dataframe(
    dataframe: pd.DataFrame,
    *,
    remove_duplicates: bool = True,
    remove_empty: bool = True,
    trim_whitespace: bool = True,
    normalize_columns: bool = False,
) -> pd.DataFrame:
    """Apply selected, non-destructive cleaning operations to a copy."""

    cleaned = dataframe.copy()
    if trim_whitespace:
        cleaned = cleaned.map(lambda value: clean_text(value) if isinstance(value, str) else value)
    if remove_empty:
        cleaned = cleaned.replace(r"^\s*$", pd.NA, regex=True).dropna(how="all")
    if remove_duplicates:
        cleaned = cleaned.drop_duplicates()
    if normalize_columns:
        used: dict[str, int] = {}
        columns: list[str] = []
        for column in cleaned.columns:
            base = normalize_column_name(column)
            used[base] = used.get(base, 0) + 1
            columns.append(base if used[base] == 1 else f"{base}_{used[base]}")
        cleaned.columns = columns
    return cleaned.reset_index(drop=True)
