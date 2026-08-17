"""Plain data containers passed between pipeline stages.

These are intentionally simple (no behavior) - they just give the loader,
parser, chunker and ingestor a shared, typed shape to hand data through.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TableBlock:
    """One table extracted from the PDF, still as raw rows."""

    rows: list[list[str]]
    page_no: int
    mode: Optional[str] = None  # "entity" | "enumeration", assigned by the table chunker


@dataclass
class Section:
    """One numbered section of the document (a product entry, a policy
    clause, ...), with its narrative text and tables collected in reading
    order."""

    section_number: int
    section_title: str
    product_name: Optional[str]
    page_no: int
    text_parts: list[str] = field(default_factory=list)
    tables: list[TableBlock] = field(default_factory=list)


@dataclass
class Chunk:
    """One unit that will become a single Weaviate object."""

    chunk_id: str
    chunk_text: str
    file_name: str
    page_no: int
    is_table: bool
    section_title: str
    product_name: Optional[str]
