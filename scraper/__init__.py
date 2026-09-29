"""Public API for the web extraction package."""

from .analyzer import AnalysisResult, PageAnalyzer
from .extractor import DataExtractor, FieldDefinition
from .pagination import PaginationConfig, PaginationMode, PaginatedExtractor

__all__ = [
    "AnalysisResult",
    "DataExtractor",
    "FieldDefinition",
    "PageAnalyzer",
    "PaginatedExtractor",
    "PaginationConfig",
    "PaginationMode",
]
