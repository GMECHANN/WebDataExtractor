"""HTML structure analysis used by the Streamlit workflow."""

from __future__ import annotations

from dataclasses import dataclass, field

from bs4 import BeautifulSoup
from soupsieve import escape

from .utils import FetchResult, clean_text, fetch_html


@dataclass(frozen=True)
class TableSummary:
    index: int
    rows: int
    columns: int
    caption: str


@dataclass(frozen=True)
class RepeatedGroup:
    label: str
    selector: str
    count: int


@dataclass(frozen=True)
class AnalysisResult:
    url: str
    status_code: int
    title: str
    table_summaries: list[TableSummary] = field(default_factory=list)
    repeated_groups: list[RepeatedGroup] = field(default_factory=list)

    @property
    def approximate_items(self) -> int:
        table_rows = sum(item.rows for item in self.table_summaries)
        repeated = max((item.count for item in self.repeated_groups), default=0)
        return max(table_rows, repeated)


class PageAnalyzer:
    """Fetch and inspect public HTML without assuming a site-specific schema."""

    def analyze_url(self, url: str, *, timeout: int = 12) -> tuple[AnalysisResult, FetchResult]:
        fetched = fetch_html(url, timeout=timeout)
        return self.analyze_html(fetched.html, url=fetched.url, status_code=fetched.status_code), fetched

    def analyze_html(self, html: str, *, url: str = "Local demo", status_code: int = 200) -> AnalysisResult:
        soup = BeautifulSoup(html, "lxml")
        title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else "Untitled page"

        tables: list[TableSummary] = []
        for index, table in enumerate(soup.select("table")):
            rows = table.select("tr")
            column_count = max((len(row.select("th, td")) for row in rows), default=0)
            caption = table.select_one("caption")
            tables.append(
                TableSummary(
                    index=index,
                    rows=max(0, len(rows) - (1 if table.select_one("thead") else 0)),
                    columns=column_count,
                    caption=clean_text(caption.get_text(" ")) if caption else f"Table {index + 1}",
                )
            )

        groups: list[RepeatedGroup] = []
        for listing in soup.select("ul, ol"):
            direct_items = listing.find_all("li", recursive=False)
            if len(direct_items) >= 2:
                element_id = listing.get("id")
                classes = listing.get("class", [])
                if element_id:
                    selector = f"#{escape(element_id)} > li"
                elif classes:
                    selector = f"{listing.name}.{escape(classes[0])} > li"
                else:
                    selector = f"{listing.name} > li"
                groups.append(RepeatedGroup("List items", selector, len(direct_items)))

        class_counts: dict[tuple[str, str], int] = {}
        for element in soup.find_all(True, class_=True):
            for class_name in element.get("class", []):
                if class_name and not class_name.startswith(("js-", "is-", "has-")):
                    key = (element.name, class_name)
                    class_counts[key] = class_counts.get(key, 0) + 1
        for (tag, class_name), count in sorted(class_counts.items(), key=lambda item: item[1], reverse=True):
            selector = f"{tag}.{escape(class_name)}"
            if count >= 3 and selector not in {item.selector for item in groups}:
                groups.append(RepeatedGroup(f"Repeated <{tag}> elements", selector, count))
            if len(groups) >= 10:
                break

        return AnalysisResult(
            url=url,
            status_code=status_code,
            title=title,
            table_summaries=tables,
            repeated_groups=groups,
        )
