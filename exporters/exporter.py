"""In-memory CSV, Excel, and JSON exports for Streamlit downloads."""

from __future__ import annotations

from io import BytesIO

import pandas as pd


class DataExporter:
    """Serialize a dataframe without writing temporary files."""

    @staticmethod
    def to_csv(dataframe: pd.DataFrame) -> bytes:
        return dataframe.to_csv(index=False).encode("utf-8-sig")

    @staticmethod
    def to_json(dataframe: pd.DataFrame) -> bytes:
        return dataframe.to_json(orient="records", indent=2, force_ascii=False).encode("utf-8")

    @staticmethod
    def to_excel(dataframe: pd.DataFrame) -> bytes:
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            dataframe.to_excel(writer, sheet_name="Extracted Data", index=False)
            worksheet = writer.sheets["Extracted Data"]
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            for column_cells in worksheet.columns:
                values = [str(cell.value or "") for cell in column_cells[:100]]
                width = min(max((len(value) for value in values), default=10) + 2, 50)
                worksheet.column_dimensions[column_cells[0].column_letter].width = width
        return output.getvalue()
