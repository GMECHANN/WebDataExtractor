"""Streamlit interface for Web Data Extractor."""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import streamlit as st

from exporters import DataExporter
from scraper import (
    DataExtractor,
    FieldDefinition,
    PageAnalyzer,
    PaginatedExtractor,
    PaginationConfig,
    PaginationMode,
)
from scraper.utils import FetchResult, WebDataExtractorError, clean_dataframe

ROOT = Path(__file__).resolve().parent
DEMO_FILE = ROOT / "examples" / "sample_catalog.html"
MAX_PREVIEW_ROWS = 100
BOOKS_URL = "https://books.toscrape.com/"
BOOKS_FIELDS = [
    {"Column Name": "Title", "CSS Selector": "h3 a", "Attribute": "title"},
    {"Column Name": "Price", "CSS Selector": ".price_color", "Attribute": "text"},
    {"Column Name": "Availability", "CSS Selector": ".availability", "Attribute": "text"},
    {"Column Name": "Link", "CSS Selector": "h3 a", "Attribute": "href"},
]
DEMO_FIELDS = [
    {"Column Name": "Product Name", "CSS Selector": ".product-title", "Attribute": "text"},
    {"Column Name": "Price", "CSS Selector": ".price", "Attribute": "text"},
    {"Column Name": "Link", "CSS Selector": "a.details", "Attribute": "href"},
]
GENERIC_FIELDS = [{"Column Name": "Name", "CSS Selector": "", "Attribute": "text"}]
THEME_PALETTES = {
    "Light": {
        "background": "#f7f9fc",
        "surface": "#ffffff",
        "surface-soft": "#eef2f7",
        "input": "#ffffff",
        "text": "#172033",
        "text-muted": "#5f6c80",
        "border": "#d7dfeb",
        "accent": "#2563eb",
        "accent-strong": "#1d4ed8",
        "accent-soft": "rgba(37, 99, 235, 0.10)",
        "on-accent": "#ffffff",
        "header": "rgba(247, 249, 252, 0.92)",
        "shadow": "rgba(15, 23, 42, 0.08)",
    },
    "Dark": {
        "background": "#0b1020",
        "surface": "#121827",
        "surface-soft": "#182132",
        "input": "#171d2b",
        "text": "#f3f6fb",
        "text-muted": "#aab5c7",
        "border": "#2b374b",
        "accent": "#60a5fa",
        "accent-strong": "#2563eb",
        "accent-soft": "rgba(96, 165, 250, 0.12)",
        "on-accent": "#ffffff",
        "header": "rgba(11, 16, 32, 0.94)",
        "shadow": "rgba(0, 0, 0, 0.28)",
    },
}
CONFIG_WIDGET_KEYS = {
    "extraction_mode": "_widget_extraction_mode",
    "container_selector": "_widget_container_selector",
    "demo_container_selector": "_widget_demo_container_selector",
    "pagination_mode": "_widget_pagination_mode",
    "maximum_pages": "_widget_maximum_pages",
    "delay_seconds": "_widget_delay_seconds",
    "next_selector": "_widget_next_selector",
    "url_pattern": "_widget_url_pattern",
}


def initialize_state() -> None:
    defaults = {
        "analysis": None,
        "first_page": None,
        "results": None,
        "stats": None,
        "is_demo_analysis": False,
        "url_input": "",
        "use_demo": False,
        "extraction_mode": "HTML Tables",
        "container_selector": "",
        "demo_container_selector": ".product-card",
        "web_field_defaults": GENERIC_FIELDS,
        "field_editor_revision": 0,
        "pagination_mode": PaginationMode.NONE.value,
        "maximum_pages": 5,
        "delay_seconds": 1.0,
        "next_selector": "",
        "url_pattern": "",
        "quick_start_loaded": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if "theme_mode" not in st.session_state:
        detected_theme = getattr(st.context.theme, "type", None)
        st.session_state.theme_mode = "Dark" if detected_theme == "dark" else "Light"


def build_theme_css(theme_mode: str) -> str:
    """Create explicit color variables independent of Streamlit's DOM scope."""

    palette = THEME_PALETTES.get(theme_mode, THEME_PALETTES["Light"])
    variables = "\n".join(f"  --wde-{name}: {value};" for name, value in palette.items())
    return f":root, .stApp {{\n{variables}\n}}"


def load_styles(theme_mode: str) -> None:
    common_styles = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
    st.markdown(
        f"<style>{common_styles}\n{build_theme_css(theme_mode)}</style>",
        unsafe_allow_html=True,
    )


def reset_results() -> None:
    st.session_state.results = None
    st.session_state.stats = None


def bind_config_widget(config_key: str) -> str:
    """Load a durable configuration value into its temporary widget key."""

    widget_key = CONFIG_WIDGET_KEYS[config_key]
    st.session_state[widget_key] = st.session_state[config_key]
    return widget_key


def persist_config_widget(config_key: str) -> None:
    """Copy a user-edited widget value back to durable configuration state."""

    st.session_state[config_key] = st.session_state[CONFIG_WIDGET_KEYS[config_key]]


def clear_application() -> None:
    """Restore extraction state without changing the user's theme choice."""

    st.session_state.analysis = None
    st.session_state.first_page = None
    st.session_state.results = None
    st.session_state.stats = None
    st.session_state.is_demo_analysis = False
    st.session_state.url_input = ""
    st.session_state.use_demo = False
    st.session_state.extraction_mode = "HTML Tables"
    st.session_state.container_selector = ""
    st.session_state.demo_container_selector = ".product-card"
    st.session_state.web_field_defaults = GENERIC_FIELDS
    st.session_state.field_editor_revision += 1
    st.session_state.pagination_mode = PaginationMode.NONE.value
    st.session_state.maximum_pages = 5
    st.session_state.delay_seconds = 1.0
    st.session_state.next_selector = ""
    st.session_state.url_pattern = ""
    st.session_state.quick_start_loaded = False
    for widget_key in CONFIG_WIDGET_KEYS.values():
        st.session_state.pop(widget_key, None)


def load_books_example() -> None:
    """Load a safe example configuration without making a network request."""

    st.session_state.url_input = BOOKS_URL
    st.session_state.use_demo = False
    st.session_state.extraction_mode = "CSS Selector"
    st.session_state.container_selector = "article.product_pod"
    st.session_state.web_field_defaults = BOOKS_FIELDS
    st.session_state.field_editor_revision += 1
    st.session_state.pagination_mode = PaginationMode.NEXT_SELECTOR.value
    st.session_state.maximum_pages = 3
    st.session_state.delay_seconds = 1.0
    st.session_state.next_selector = "li.next a"
    st.session_state.url_pattern = ""
    st.session_state.analysis = None
    st.session_state.first_page = None
    st.session_state.results = None
    st.session_state.stats = None
    st.session_state.is_demo_analysis = False
    st.session_state.quick_start_loaded = True


def show_analysis() -> None:
    analysis = st.session_state.analysis
    if analysis is None:
        st.info("Analyze a public URL or the bundled demo to reveal extraction options.")
        return
    st.subheader("Website analysis")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("HTTP status", analysis.status_code)
    col2.metric("HTML tables", len(analysis.table_summaries))
    col3.metric("Repeated groups", len(analysis.repeated_groups))
    col4.metric("Approx. items", analysis.approximate_items)
    source_label = "Bundled local demo" if st.session_state.is_demo_analysis else analysis.url
    st.caption(f"**Page:** {analysis.title}  ·  **Source:** {source_label}")
    if not analysis.table_summaries and not analysis.repeated_groups:
        st.warning("No obvious tables or repeated elements were detected. You can still try custom CSS selectors.")


def extraction_controls() -> tuple[str, dict]:
    analysis = st.session_state.analysis
    mode = st.selectbox(
        "Extraction mode",
        ["HTML Tables", "CSS Selector", "Simple Lists"],
        key=bind_config_widget("extraction_mode"),
        on_change=persist_config_widget,
        args=("extraction_mode",),
    )
    options: dict = {}

    if mode == "HTML Tables":
        summaries = analysis.table_summaries if analysis else []
        if summaries:
            labels = [f"{item.caption} — {item.rows} rows × {item.columns} columns" for item in summaries]
            selected = st.selectbox("Table", range(len(labels)), format_func=lambda index: labels[index])
            options["table_index"] = selected
        else:
            st.warning("No HTML table is available in the current analysis.")
            options["table_index"] = 0

    elif mode == "CSS Selector":
        container_key = "demo_container_selector" if st.session_state.is_demo_analysis else "container_selector"
        options["container"] = st.text_input(
            "Container selector",
            placeholder=".product-card",
            help="One container should represent one output row.",
            key=bind_config_widget(container_key),
            on_change=persist_config_widget,
            args=(container_key,),
        )
        if st.session_state.is_demo_analysis:
            defaults = pd.DataFrame(DEMO_FIELDS)
            editor_key = "field_editor_demo"
        else:
            defaults = pd.DataFrame(st.session_state.web_field_defaults)
            editor_key = f"field_editor_web_{st.session_state.field_editor_revision}"
        options["fields"] = st.data_editor(
            defaults,
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            column_config={
                "Column Name": st.column_config.TextColumn(required=True),
                "CSS Selector": st.column_config.TextColumn(required=True),
                "Attribute": st.column_config.TextColumn(
                    help="Use text, href, src, title, or another HTML attribute.",
                ),
            },
            key=editor_key,
        )

    else:
        groups = analysis.repeated_groups if analysis else []
        detected = [item.selector for item in groups]
        labels = {item.selector: f"{item.selector} — {item.count} items" for item in groups}
        default_selector = "#categories > li" if st.session_state.is_demo_analysis else (detected[0] if detected else "")
        if detected:
            selected = st.selectbox(
                "Detected group",
                detected,
                index=detected.index(default_selector) if default_selector in detected else 0,
                format_func=lambda value: labels[value],
            )
        else:
            selected = ""
        options["list_selector"] = st.text_input(
            "List item selector",
            value=selected or default_selector,
            placeholder="ul.results > li",
        )
    return mode, options


def build_extraction(mode: str, options: dict):
    extractor = DataExtractor()
    if mode == "HTML Tables":
        return lambda html, base_url: extractor.extract_table(html, int(options["table_index"]))
    if mode == "CSS Selector":
        fields = [
            FieldDefinition(str(row["Column Name"]), str(row["CSS Selector"]), str(row["Attribute"] or "text"))
            for _, row in options["fields"].fillna("").iterrows()
        ]
        return lambda html, base_url: extractor.extract_fields(
            html, options["container"], fields, base_url=base_url
        )
    return lambda html, base_url: extractor.extract_list(html, options["list_selector"], base_url=base_url)


def show_results() -> None:
    dataframe = st.session_state.results
    stats = st.session_state.stats
    if dataframe is None or stats is None:
        return

    st.divider()
    st.subheader("Extraction results")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Rows", f"{len(dataframe):,}")
    col2.metric("Columns", len(dataframe.columns))
    col3.metric("Pages", stats["pages"])
    col4.metric("Processing time", f"{stats['seconds']:.2f}s")

    if dataframe.empty:
        st.warning("The extraction completed, but no data rows were found.")
        return
    st.dataframe(dataframe.head(MAX_PREVIEW_ROWS), width="stretch", hide_index=True)
    if len(dataframe) > MAX_PREVIEW_ROWS:
        st.caption(f"Preview limited to the first {MAX_PREVIEW_ROWS} rows. Downloads contain all rows.")

    st.subheader("Download")
    export = DataExporter()
    csv_col, excel_col, json_col = st.columns(3)
    csv_col.download_button(
        "Download CSV", export.to_csv(dataframe), "web_data.csv", "text/csv", width="stretch"
    )
    excel_col.download_button(
        "Download Excel", export.to_excel(dataframe), "web_data.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch"
    )
    json_col.download_button(
        "Download JSON", export.to_json(dataframe), "web_data.json", "application/json", width="stretch"
    )


def main() -> None:
    st.set_page_config(page_title="Web Data Extractor", page_icon="◫", layout="wide")
    initialize_state()
    load_styles(st.session_state.theme_mode)

    st.markdown('<div class="app-kicker">Responsible extraction toolkit</div>', unsafe_allow_html=True)
    st.markdown('<h1 class="app-title">Web Data Extractor</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="app-subtitle">Extract structured web data and export it to Excel, CSV or JSON.</p>',
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("Configuration")
        st.segmented_control(
            "Theme",
            ["Light", "Dark"],
            key="theme_mode",
            width="stretch",
        )
        timeout = st.slider("Request timeout", 5, 30, 12, 1, help="Seconds per HTTP request.")
        st.subheader("Data cleaning")
        remove_duplicates = st.checkbox("Remove duplicate rows", True)
        remove_empty = st.checkbox("Remove empty rows", True)
        trim_whitespace = st.checkbox("Trim whitespace", True)
        normalize_columns = st.checkbox("Normalize column names", False)
        st.caption("Only publicly accessible HTML is supported. Access restrictions are never bypassed.")

    source_col, demo_col = st.columns([3, 1])
    with demo_col:
        use_demo = st.toggle(
            "Use bundled demo",
            help="Loads local sample HTML; no request is sent.",
            key="use_demo",
        )
    with source_col:
        url = st.text_input(
            "Website URL",
            placeholder="https://example.com/catalog",
            disabled=use_demo,
            help="Only public HTTP and HTTPS pages are accepted.",
            key="url_input",
        )

    with st.expander("Quick start example", expanded=False):
        quick_text, quick_action = st.columns([4, 1])
        quick_text.markdown(
            "Try **Books to Scrape**, a public sandbox created for web-scraping practice. "
            "Loading the example only fills the form; it does not send a request."
        )
        quick_action.button(
            "Load example configuration",
            on_click=load_books_example,
            width="stretch",
        )
        st.caption(
            "CSS container: `article.product_pod` · Pagination: `li.next a` · "
            "3 pages · 1 second between requests"
        )
    if st.session_state.quick_start_loaded:
        st.success("Example loaded. Select Analyze Website when you are ready to make the first request.")
        st.session_state.quick_start_loaded = False

    analyze_col, clear_col, spacer = st.columns([1, 1, 4])
    analyze_clicked = analyze_col.button("Analyze Website", type="primary", width="stretch")
    clear_col.button("Clear", width="stretch", on_click=clear_application)

    if analyze_clicked:
        reset_results()
        try:
            with st.spinner("Inspecting page structure…"):
                analyzer = PageAnalyzer()
                if use_demo:
                    html = DEMO_FILE.read_text(encoding="utf-8")
                    result = analyzer.analyze_html(html, url="demo://sample-catalog", status_code=200)
                    fetched = FetchResult("https://demo.local/sample-catalog", 200, html, "text/html")
                else:
                    result, fetched = analyzer.analyze_url(url, timeout=timeout)
                st.session_state.analysis = result
                st.session_state.first_page = fetched
                st.session_state.is_demo_analysis = use_demo
            st.success("Analysis complete. Review the detected structure below.")
        except WebDataExtractorError as exc:
            st.error(str(exc))
        except Exception:
            st.error("The page could not be analyzed because it returned unexpected content.")

    show_analysis()

    if st.session_state.analysis is not None:
        st.divider()
        st.subheader("Extraction setup")
        mode, extraction_options = extraction_controls()

        with st.expander("Pagination", expanded=False):
            if st.session_state.is_demo_analysis:
                st.caption("Pagination is disabled for the bundled single-page demo.")
                pagination_mode = PaginationMode.NONE
                maximum_pages, delay_seconds, next_selector, url_pattern = 1, 1.0, "", ""
            else:
                pagination_mode = PaginationMode(
                    st.selectbox(
                        "Method",
                        [item.value for item in PaginationMode],
                        key=bind_config_widget("pagination_mode"),
                        on_change=persist_config_widget,
                        args=("pagination_mode",),
                    )
                )
                maximum_pages = st.number_input(
                    "Maximum pages",
                    min_value=1,
                    max_value=20,
                    step=1,
                    key=bind_config_widget("maximum_pages"),
                    on_change=persist_config_widget,
                    args=("maximum_pages",),
                )
                delay_seconds = st.number_input(
                    "Pause between requests (seconds)",
                    min_value=0.5,
                    max_value=10.0,
                    step=0.5,
                    key=bind_config_widget("delay_seconds"),
                    on_change=persist_config_widget,
                    args=("delay_seconds",),
                )
                next_selector = ""
                url_pattern = ""
                if pagination_mode == PaginationMode.NEXT_SELECTOR:
                    next_selector = st.text_input(
                        "Next button CSS selector",
                        placeholder="a.next",
                        key=bind_config_widget("next_selector"),
                        on_change=persist_config_widget,
                        args=("next_selector",),
                    )
                elif pagination_mode == PaginationMode.URL_PATTERN:
                    url_pattern = st.text_input(
                        "URL pattern", placeholder="https://example.com/items?page={page}",
                        help='Include the literal placeholder "{page}".',
                        key=bind_config_widget("url_pattern"),
                        on_change=persist_config_widget,
                        args=("url_pattern",),
                    )

        if st.button("Extract Data", type="primary"):
            started = time.perf_counter()
            progress = st.progress(0, text="Preparing extraction…")
            try:
                extraction = build_extraction(mode, extraction_options)
                config = PaginationConfig(
                    mode=pagination_mode,
                    maximum_pages=int(maximum_pages),
                    delay_seconds=float(delay_seconds),
                    next_selector=next_selector,
                    url_pattern=url_pattern,
                )
                runner = PaginatedExtractor()
                result = runner.run(
                    st.session_state.first_page,
                    extraction,
                    config,
                    timeout=timeout,
                    progress_callback=lambda current, total: progress.progress(
                        min(current / total, 1.0), text=f"Processed page {current} of up to {total}…"
                    ),
                )
                cleaned = clean_dataframe(
                    result.dataframe,
                    remove_duplicates=remove_duplicates,
                    remove_empty=remove_empty,
                    trim_whitespace=trim_whitespace,
                    normalize_columns=normalize_columns,
                )
                st.session_state.results = cleaned
                st.session_state.stats = {
                    "pages": result.pages_processed,
                    "seconds": time.perf_counter() - started,
                }
                progress.progress(1.0, text="Extraction complete.")
                if cleaned.empty:
                    st.warning("No data remained after extraction and cleaning. Review the selectors and options.")
                else:
                    st.success(f"Extracted {len(cleaned):,} rows successfully.")
            except WebDataExtractorError as exc:
                progress.empty()
                st.error(str(exc))
            except Exception:
                progress.empty()
                st.error("Extraction stopped because the page structure was not in the expected format.")

    show_results()


if __name__ == "__main__":
    main()
