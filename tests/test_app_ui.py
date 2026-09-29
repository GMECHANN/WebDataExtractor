"""UI regression tests for non-network Streamlit workflows."""

from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app import build_theme_css
from scraper.analyzer import PageAnalyzer
from scraper.utils import FetchResult


BOOKS_HTML = """
<html><head><title>Books to Scrape</title></head><body>
<article class="product_pod"><h3><a title="Book" href="catalogue/book.html">Book</a></h3></article>
</body></html>
"""


def fake_books_analysis():
    analyzer = PageAnalyzer()
    result = analyzer.analyze_html(BOOKS_HTML, url="https://books.toscrape.com/", status_code=200)
    fetched = FetchResult("https://books.toscrape.com/", 200, BOOKS_HTML, "text/html")
    return result, fetched


def test_custom_styles_use_complete_explicit_theme_tokens() -> None:
    styles_path = Path(__file__).resolve().parents[1] / "assets" / "styles.css"
    styles = styles_path.read_text(encoding="utf-8").lower()

    for token in ["--wde-background", "--wde-surface", "--wde-input", "--wde-text", "--wde-border"]:
        assert token in styles
    light_css = build_theme_css("Light")
    dark_css = build_theme_css("Dark")
    assert "--wde-background: #f7f9fc" in light_css
    assert "--wde-background: #0b1020" in dark_css
    assert light_css != dark_css


def test_quick_start_loads_books_configuration_without_request() -> None:
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(app_path, default_timeout=20)
    app.run()
    assert not app.exception

    next(button for button in app.button if button.label == "Load example configuration").click()
    app.run()

    assert not app.exception
    assert app.session_state["url_input"] == "https://books.toscrape.com/"
    assert app.session_state["use_demo"] is False
    assert app.session_state["extraction_mode"] == "CSS Selector"
    assert app.session_state["container_selector"] == "article.product_pod"
    assert app.session_state["pagination_mode"] == "Next button CSS selector"
    assert app.session_state["next_selector"] == "li.next a"
    assert app.session_state["maximum_pages"] == 3
    assert app.session_state["delay_seconds"] == 1.0
    assert app.session_state["web_field_defaults"] == [
        {"Column Name": "Title", "CSS Selector": "h3 a", "Attribute": "title"},
        {"Column Name": "Price", "CSS Selector": ".price_color", "Attribute": "text"},
        {"Column Name": "Availability", "CSS Selector": ".availability", "Attribute": "text"},
        {"Column Name": "Link", "CSS Selector": "h3 a", "Attribute": "href"},
    ]
    assert app.session_state["analysis"] is None
    assert app.session_state["first_page"] is None

    with patch.object(PageAnalyzer, "analyze_url", return_value=fake_books_analysis()):
        next(button for button in app.button if button.label == "Analyze Website").click()
        app.run()

    assert not app.exception
    assert app.selectbox(key="_widget_extraction_mode").value == "CSS Selector"
    assert app.text_input(key="_widget_container_selector").value == "article.product_pod"
    assert app.selectbox(key="_widget_pagination_mode").value == "Next button CSS selector"
    assert app.text_input(key="_widget_next_selector").value == "li.next a"
    assert app.number_input(key="_widget_maximum_pages").value == 3
    assert app.number_input(key="_widget_delay_seconds").value == 1.0
    assert [field["Column Name"] for field in app.session_state["web_field_defaults"]] == [
        "Title",
        "Price",
        "Availability",
        "Link",
    ]

    app.segmented_control(key="theme_mode").set_value("Dark")
    app.run()
    assert app.session_state["extraction_mode"] == "CSS Selector"
    assert app.session_state["container_selector"] == "article.product_pod"
    assert app.session_state["pagination_mode"] == "Next button CSS selector"

    app.text_input(key="_widget_container_selector").set_value("article.custom_book")
    app.run()
    assert app.session_state["container_selector"] == "article.custom_book"

    next(button for button in app.button if button.label == "Clear").click()
    app.run()
    assert app.session_state["analysis"] is None
    assert app.session_state["extraction_mode"] == "HTML Tables"
    assert app.session_state["container_selector"] == ""
    assert app.session_state["pagination_mode"] == "No pagination"
    assert app.session_state["theme_mode"] == "Dark"


def test_bundled_demo_table_flow_still_extracts_and_exports() -> None:
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(app_path, default_timeout=20)
    app.run()
    app.toggle(key="use_demo").set_value(True)
    app.run()
    next(button for button in app.button if button.label == "Analyze Website").click()
    app.run()
    next(button for button in app.button if button.label == "Extract Data").click()
    app.run()

    assert not app.exception
    assert app.session_state["results"].shape == (4, 4)
    assert app.session_state["stats"]["pages"] == 1
    assert len(app.download_button) == 3
