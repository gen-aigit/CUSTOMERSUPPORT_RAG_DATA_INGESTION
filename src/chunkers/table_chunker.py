"""Turns a table's rows into one or more plain-text chunks, depending on
what the table represents:

- entity table (e.g. "Specifications", "Device Compatibility"): rows are
  attributes of ONE subject -> the whole table becomes a single chunk, so a
  query about e.g. battery life gets the full spec context alongside it,
  and a lone "Battery life: 7 hours" row without that context wouldn't be
  useful on its own.
- enumeration table (e.g. a Symptom/Cause/Fix table): rows are independent,
  parallel records -> each row becomes its own chunk, so a query about one
  symptom isn't diluted by four unrelated symptoms sharing one embedding.

Mode is decided from the table's header row, defaulting to "entity" (the
safer choice - it under-splits an unrecognized table instead of shredding
it into meaningless single-row fragments).

product_specs' own tables ("Specifications", "Device Compatibility") are
both entity tables, so enumeration mode isn't exercised by this collection
today - it's here because the same loader/parser/chunker pipeline is meant
to be reused for refund_specs and technical_support_guide, whose tables
(Symptom/Cause/Fix, Return Window by category, ...) are enumeration tables.
"""

from src.models.schema import TableBlock
from src.utils.logger import get_logger

logger = get_logger(__name__)

_ENUMERATION_HEADER_KEYWORDS = {
    "symptom",
    "category",
    "return reason",
    "condition",
    "original payment method",
}


def assign_table_mode(table: TableBlock) -> str:
    if not table.rows:
        return "entity"
    header = (table.rows[0][0] or "").strip().lower()
    return "enumeration" if header in _ENUMERATION_HEADER_KEYWORDS else "entity"


def table_to_chunk_texts(table: TableBlock) -> list[str]:
    if not table.rows:
        return []

    mode = table.mode or assign_table_mode(table)
    headers, data_rows = table.rows[0], table.rows[1:]
    if not data_rows:
        return []

    formatted_rows = [row for row in (_format_row(headers, r) for r in data_rows) if row]
    if not formatted_rows:
        return []

    if mode == "enumeration":
        return formatted_rows

    return ["\n".join(formatted_rows)]


def _format_row(headers: list[str], row: list[str]) -> str:
    """2-column table (Specification/Detail style) -> "Key: Value".
    Wider table (a comparison matrix) -> "RowLabel — Col: Val, Col: Val"."""

    if len(row) == 2:
        key, value = row[0].strip(), row[1].strip()
        return f"{key}: {value}" if key and value else ""

    label = (row[0] or "").strip()
    rest = ", ".join(
        f"{headers[i].strip()}: {row[i].strip()}"
        for i in range(1, len(row))
        if i < len(headers) and row[i].strip()
    )
    if label and rest:
        return f"{label} — {rest}"
    return label or rest
