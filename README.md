# Web Data Extractor

Web Data Extractor is a Streamlit application for turning publicly accessible HTML into structured datasets. It analyzes a page, helps identify tables and repeated elements, extracts records with several strategies, applies practical cleaning rules, and generates CSV, Excel, or JSON downloads.

The project is designed as a clear, modular portfolio example of Python development, responsible web scraping, data processing, error handling, and file export.

## Features

- Analyze a public HTTP or HTTPS page and report its status, title, tables, and repeated element groups.
- Extract native HTML tables.
- Build records from a container selector and multiple custom fields.
- Read element text, `href`, `src`, `title`, or another HTML attribute.
- Extract text and links from simple lists or other repeated elements.
- Follow a next-link selector or a `{page}` URL pattern, with a configurable page cap and delay.
- Remove duplicate or empty rows, trim whitespace, and normalize column names.
- Preview a bounded number of rows and review row, column, page, and timing statistics.
- Download all results as UTF-8 CSV, `.xlsx`, or JSON.
- Run a complete demonstration from bundled HTML without relying on an external website.

## Technologies

- Python
- Streamlit
- Requests
- Beautiful Soup 4
- pandas
- openpyxl
- lxml
- pytest

## Installation

Python 3.10 or newer is recommended.

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\activate
```

Install the dependencies:

```powershell
pip install -r requirements.txt
```

## Run the application

```powershell
python -m streamlit run app.py
```

Streamlit will print the local application address in the terminal and normally open it in a browser.

## Usage

1. Enter a public page URL, or enable **Use bundled demo**.
2. Select **Analyze Website** to inspect the available structures.
3. Choose **HTML Tables**, **CSS Selector**, or **Simple Lists**.
4. Configure selectors and optional, conservative pagination.
5. Select cleaning options in the sidebar, then choose **Extract Data**.
6. Review the preview and statistics, then download CSV, Excel, or JSON.

### Bundled demo

Enable **Use bundled demo**, then select **Analyze Website**. Good demo paths include:

- **HTML Tables**: extract the detected “Current inventory” table.
- **CSS Selector**: keep `.product-card` as the container and use the prefilled fields.
- **Simple Lists**: use `#categories > li`.

The demo is loaded from `examples/sample_catalog.html`; it sends no network request and supports the same preview, cleaning, and export workflow.

### Demo example: Books to Scrape

[Books to Scrape](https://books.toscrape.com/) is a public sandbox website specifically created for practicing web scraping. Open **Quick start example** and select **Load example configuration** to populate the following settings without starting a request:

- URL: `https://books.toscrape.com/`
- Extraction mode: **CSS Selector**
- Container: `article.product_pod`
- Fields:

  | Column Name | CSS Selector | Attribute |
  | --- | --- | --- |
  | Title | `h3 a` | `title` |
  | Price | `.price_color` | `text` |
  | Availability | `.availability` | `text` |
  | Link | `h3 a` | `href` |

- Pagination: **Next button CSS selector**
- Next link: `li.next a`
- Maximum pages: `3`
- Pause: `1` second

Review the loaded values, then select **Analyze Website** and **Extract Data**. Relative book links are resolved to complete URLs during extraction. Keep the request delay enabled and use the example only for its intended educational purpose.

### Theme behavior

Use the **Light / Dark** selector in the application sidebar. On the first load, the application uses Streamlit's current theme as its initial choice, then applies a complete explicit palette to the main content, sidebar, header, cards, inputs, expanders, messages, tables, and download controls. This avoids mixed-theme screens when Streamlit's internal theme variables are scoped differently across versions.

### CSS field model

Each matching container becomes one row. A field consists of:

| Column Name | CSS Selector | Attribute |
| --- | --- | --- |
| Product Name | `.title` | `text` |
| Price | `.price` | `text` |
| Image | `img` | `src` |
| Link | `a` | `href` |

Relative links and image paths are resolved against the page URL.

## Supported export formats

- **CSV**: UTF-8 with a byte-order mark for convenient Excel compatibility.
- **Excel**: `.xlsx` workbook with a frozen header, filters, and adjusted column widths.
- **JSON**: indented array of record objects using Unicode characters directly.

Exports are built in memory. The application does not write scraped output to disk.

## Project structure

```text
WebDataExtractor/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── assets/
│   └── styles.css
├── examples/
│   └── sample_catalog.html
├── exporters/
│   ├── __init__.py
│   └── exporter.py
├── scraper/
│   ├── __init__.py
│   ├── analyzer.py
│   ├── extractor.py
│   ├── pagination.py
│   └── utils.py
└── tests/
    ├── test_app_ui.py
    ├── test_basic.py
    └── test_network_and_pagination.py
```

## Tests

Run the test suite from the project directory:

```powershell
python -m pytest -q
```

The tests cover URL validation, text and dataframe cleaning, CSS selector extraction, generated selectors, HTTP redirects and error messages, bounded pagination, structural analysis, and all three export formats.

## Ethical scraping notice

Use this application only with public content you are permitted to access. Review the website's terms, `robots.txt`, applicable laws, and the impact of your requests. Keep page limits low and delays reasonable. The application identifies its HTTP client, applies timeouts, limits responses to 5 MB, validates redirect targets, and does not bypass authentication, CAPTCHAs, paywalls, access controls, or anti-bot systems.

## Limitations

- The extractor processes server-rendered HTML and does not execute JavaScript.
- It does not authenticate or manage logged-in sessions.
- Automatic repeated-element detection is heuristic and may require manual selectors.
- Pagination supports only a next-link CSS selector or a URL pattern.
- It does not interpret `robots.txt` automatically; the user remains responsible for checking site policy.
- Complex nested tables, malformed markup, and changing layouts may require site-specific adjustments.
- Private, loopback, link-local, and other non-public network destinations are intentionally blocked.

## Possible future improvements

- Save and reload extraction templates.
- Offer an interactive selector picker.
- Add optional `robots.txt` guidance before extraction.
- Add type inference and per-column transformations.
- Add scheduled jobs and persistent run history in an explicitly configured deployment.
- Expand test coverage with mocked HTTP redirects and pagination flows.
