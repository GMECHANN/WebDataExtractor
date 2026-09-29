"""Focused tests for validation, cleaning, extraction, and export."""

from io import BytesIO

import pandas as pd
import pytest

from exporters import DataExporter
from scraper.extractor import DataExtractor, ExtractionError, FieldDefinition
from scraper.utils import InvalidURLError, clean_dataframe, clean_text, validate_url


SAMPLE_HTML = """
<html><body>
  <section class="card"><h2>  Alpha   Lamp </h2><a href="/alpha">Details</a></section>
  <section class="card"><h2>Beta Desk</h2><a href="https://example.com/beta">Details</a></section>
</body></html>
"""


@pytest.mark.parametrize(
    "url",
    ["https://example.com/products", "http://example.org:8080/path?q=data"],
)
def test_validate_url_accepts_http_urls(url: str) -> None:
    assert validate_url(url) == url


@pytest.mark.parametrize(
    "url",
    ["", "ftp://example.com/file", "http://localhost/admin", "http://127.0.0.1", "https://user:pass@example.com"],
)
def test_validate_url_rejects_unsafe_or_invalid_urls(url: str) -> None:
    with pytest.raises(InvalidURLError):
        validate_url(url)


def test_text_and_dataframe_cleaning() -> None:
    assert clean_text("  a\n  useful\t value ") == "a useful value"
    frame = pd.DataFrame({"Product Name": [" Lamp ", " Lamp ", "  "]})
    result = clean_dataframe(frame, normalize_columns=True)
    assert list(result.columns) == ["product_name"]
    assert result.to_dict(orient="records") == [{"product_name": "Lamp"}]


def test_selector_extraction_supports_text_and_attributes() -> None:
    result = DataExtractor().extract_fields(
        SAMPLE_HTML,
        ".card",
        [FieldDefinition("name", "h2", "text"), FieldDefinition("link", "a", "href")],
        base_url="https://example.com/catalog/",
    )
    assert result.to_dict(orient="records") == [
        {"name": "Alpha Lamp", "link": "https://example.com/alpha"},
        {"name": "Beta Desk", "link": "https://example.com/beta"},
    ]


def test_selector_extraction_supports_title_attribute() -> None:
    html = '<article class="book"><h3><a title="A useful book" href="catalogue/book.html">Book</a></h3></article>'
    result = DataExtractor().extract_fields(
        html,
        "article.book",
        [FieldDefinition("Title", "h3 a", "title"), FieldDefinition("Link", "h3 a", "href")],
        base_url="https://example.com/",
    )

    assert result.to_dict(orient="records") == [
        {"Title": "A useful book", "Link": "https://example.com/catalogue/book.html"}
    ]


def test_invalid_selector_has_friendly_error() -> None:
    with pytest.raises(ExtractionError, match="invalid"):
        DataExtractor().extract_list(SAMPLE_HTML, "[broken")


def test_custom_fields_require_unique_column_names() -> None:
    fields = [
        FieldDefinition("name", "h2", "text"),
        FieldDefinition("name", "a", "text"),
    ]
    with pytest.raises(ExtractionError, match="unique"):
        DataExtractor().extract_fields(SAMPLE_HTML, ".card", fields)


def test_dataframe_exports_are_readable() -> None:
    frame = pd.DataFrame([{"name": "Café", "price": 12.5}])
    csv_data = DataExporter.to_csv(frame)
    json_data = DataExporter.to_json(frame)
    excel_data = DataExporter.to_excel(frame)

    assert "Café" in csv_data.decode("utf-8-sig")
    assert '"Café"' in json_data.decode("utf-8")
    restored = pd.read_excel(BytesIO(excel_data))
    pd.testing.assert_frame_equal(restored, frame)
