"""Extraction strategies for tables, custom CSS fields, and simple lists."""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup
from soupsieve import SelectorSyntaxError

from .utils import WebDataExtractorError, clean_text


class ExtractionError(WebDataExtractorError):
    """Raised when a requested structure cannot be extracted."""


@dataclass(frozen=True)
class FieldDefinition:
    name: str
    selector: str
    attribute: str = "text"


class DataExtractor:
    """Extract structured records from an HTML document."""

    def extract_table(self, html: str, table_index: int = 0) -> pd.DataFrame:
        soup = BeautifulSoup(html, "lxml")
        tables = soup.select("table")
        if not tables:
            raise ExtractionError("No HTML tables were found on this page.")
        if table_index < 0 or table_index >= len(tables):
            raise ExtractionError("The selected table is no longer available.")
        try:
            frames = pd.read_html(StringIO(str(tables[table_index])))
        except (ValueError, ImportError) as exc:
            raise ExtractionError("The selected table could not be converted to rows and columns.") from exc
        if not frames or frames[0].empty:
            raise ExtractionError("The selected table is empty.")
        return frames[0]

    def extract_fields(
        self,
        html: str,
        container_selector: str,
        fields: list[FieldDefinition],
        *,
        base_url: str = "",
    ) -> pd.DataFrame:
        if not clean_text(container_selector):
            raise ExtractionError("Enter a container CSS selector.")
        valid_fields = [field for field in fields if clean_text(field.name) and clean_text(field.selector)]
        if not valid_fields:
            raise ExtractionError("Add at least one field with a column name and CSS selector.")
        field_names = [clean_text(field.name) for field in valid_fields]
        if len(field_names) != len(set(field_names)):
            raise ExtractionError("Each custom field must have a unique column name.")

        soup = BeautifulSoup(html, "lxml")
        try:
            containers = soup.select(container_selector)
        except SelectorSyntaxError as exc:
            raise ExtractionError("The container CSS selector is invalid.") from exc
        if not containers:
            raise ExtractionError("The container selector did not match any elements.")

        records: list[dict[str, str]] = []
        for container in containers:
            record: dict[str, str] = {}
            for field in valid_fields:
                try:
                    element = container.select_one(field.selector)
                except SelectorSyntaxError as exc:
                    raise ExtractionError(f'The selector for "{field.name}" is invalid.') from exc
                if element is None:
                    record[field.name] = ""
                    continue
                attribute = clean_text(field.attribute).lower() or "text"
                if attribute == "text":
                    value = element.get_text(" ", strip=True)
                else:
                    value = element.get(attribute, "")
                    if attribute in {"href", "src"} and value and base_url:
                        value = urljoin(base_url, value)
                record[field.name] = clean_text(value)
            records.append(record)
        return pd.DataFrame(records)

    def extract_list(self, html: str, selector: str, *, base_url: str = "") -> pd.DataFrame:
        if not clean_text(selector):
            raise ExtractionError("Enter or select a list item CSS selector.")
        soup = BeautifulSoup(html, "lxml")
        try:
            elements = soup.select(selector)
        except SelectorSyntaxError as exc:
            raise ExtractionError("The list CSS selector is invalid.") from exc
        if not elements:
            raise ExtractionError("The list selector did not match any elements.")

        records = []
        for element in elements:
            link = element if element.name == "a" else element.select_one("a[href]")
            records.append(
                {
                    "text": clean_text(element.get_text(" ", strip=True)),
                    "link": urljoin(base_url, link.get("href", "")) if link else "",
                }
            )
        return pd.DataFrame(records)
