"""Turns a PDF into one ordered list of "page elements" (text lines and
tables, top-to-bottom, page by page) that src/parsers/section_parser.py then
groups into sections.

Two things this module handles that a naive `extract_text()` /
`extract_tables()` call would get wrong:
  1. Narrative text and tables must be kept apart, but still in reading
     order - so a table isn't lost inside the surrounding paragraph text.
  2. A table can be cut in half by a page break (this actually happens in
     the sample product catalog: the "Device Compatibility" table for
     AuroraBuds Pro 2 has 3 rows on page 1 and a 4th row at the top of
     page 2). Left unmerged, that becomes two broken table fragments
     instead of one - so consecutive pages are checked for a continuing
     table and merged before anything downstream sees them.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pdfplumber

from src.utils.logger import get_logger

logger = get_logger(__name__)

# How close to the page edge a table has to be for us to suspect it
# continues onto/from the next page. Generous on purpose - a false-positive
# merge check just costs a cheap comparison, a missed one silently breaks a
# table.
_BOTTOM_EDGE_MARGIN_PT = 80
_TOP_EDGE_MARGIN_PT = 120
_LINE_GROUPING_TOLERANCE_PT = 3.0


@dataclass
class PageElement:
    kind: str  # "text_line" | "table"
    page_no: int
    top: float
    text: Optional[str] = None
    rows: Optional[list[list[str]]] = None


def load_pdf_elements(pdf_path: Path) -> list[PageElement]:
    """Returns every text line and table in the PDF, in reading order,
    with cross-page table continuations already merged."""

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pages_elements: list[list[PageElement]] = []
    page_heights: list[float] = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                try:
                    elements = _process_page(page, page_index)
                except Exception:
                    logger.exception(
                        "Failed to parse page %s of %s - skipping this page, "
                        "continuing with the rest of the document",
                        page_index,
                        pdf_path.name,
                    )
                    elements = []
                pages_elements.append(elements)
                page_heights.append(page.height)
    except Exception as exc:
        logger.exception("Could not open/read PDF %s", pdf_path)
        raise RuntimeError(f"Could not open/read PDF {pdf_path}: {exc}") from exc

    _merge_table_continuations(pages_elements, page_heights)

    all_elements = [element for page_elements in pages_elements for element in page_elements]
    logger.info(
        "Loaded %s pages, %s elements (%s tables, %s text lines) from %s",
        len(pages_elements),
        len(all_elements),
        sum(1 for e in all_elements if e.kind == "table"),
        sum(1 for e in all_elements if e.kind == "text_line"),
        pdf_path.name,
    )
    return all_elements


def _process_page(page, page_no: int) -> list[PageElement]:
    tables = page.find_tables()
    table_bboxes = [t.bbox for t in tables]

    elements: list[PageElement] = [
        PageElement(kind="table", page_no=page_no, top=t.bbox[1], rows=_clean_rows(t.extract()))
        for t in tables
    ]

    filtered_page = page.filter(lambda obj: not _char_in_any_bbox(obj, table_bboxes))
    words = filtered_page.extract_words()
    for line in _group_words_into_lines(words):
        if line["text"].strip():
            elements.append(
                PageElement(kind="text_line", page_no=page_no, top=line["top"], text=line["text"])
            )

    elements.sort(key=lambda e: e.top)
    return elements


def _clean_rows(rows: list[list[Optional[str]]]) -> list[list[str]]:
    return [[(cell or "").strip() for cell in row] for row in rows]


def _char_in_any_bbox(obj: dict, bboxes: list[tuple]) -> bool:
    for x0, top, x1, bottom in bboxes:
        if obj["x0"] >= x0 - 1 and obj["x1"] <= x1 + 1 and obj["top"] >= top - 1 and obj["bottom"] <= bottom + 1:
            return True
    return False


def _group_words_into_lines(words: list[dict]) -> list[dict]:
    """pdfplumber gives words with positions, not lines - group them into
    lines ourselves using vertical proximity."""

    lines: list[dict] = []
    current_top: Optional[float] = None
    current_words: list[dict] = []

    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if current_top is not None and abs(word["top"] - current_top) > _LINE_GROUPING_TOLERANCE_PT:
            lines.append(_finalize_line(current_words))
            current_words = []
        current_words.append(word)
        current_top = word["top"]

    if current_words:
        lines.append(_finalize_line(current_words))

    return lines


def _finalize_line(words: list[dict]) -> dict:
    words_sorted = sorted(words, key=lambda w: w["x0"])
    return {
        "text": " ".join(w["text"] for w in words_sorted),
        "top": min(w["top"] for w in words_sorted),
    }


def _merge_table_continuations(pages_elements: list[list[PageElement]], page_heights: list[float]) -> None:
    """If the last element on page N is a table sitting near the bottom of
    the page, and the very first element on page N+1 is a table near the
    top with the same column count, treat them as one table split by the
    page break and merge the rows into the page-N table."""

    for i in range(len(pages_elements) - 1):
        current_page = pages_elements[i]
        next_page = pages_elements[i + 1]
        if not current_page or not next_page:
            continue

        last_element = current_page[-1]
        first_element = next_page[0]

        if last_element.kind != "table" or first_element.kind != "table":
            continue

        table_bottom_estimate = last_element.top + _estimate_table_height(last_element.rows)
        near_bottom = table_bottom_estimate >= page_heights[i] - _BOTTOM_EDGE_MARGIN_PT
        near_top = first_element.top <= _TOP_EDGE_MARGIN_PT
        same_width = last_element.rows and first_element.rows and len(last_element.rows[0]) == len(first_element.rows[0])

        if near_bottom and near_top and same_width:
            logger.info(
                "Merging table continuation across pages %s -> %s (%s + %s rows)",
                last_element.page_no,
                first_element.page_no,
                len(last_element.rows),
                len(first_element.rows),
            )
            last_element.rows.extend(first_element.rows)
            next_page.pop(0)


def _estimate_table_height(rows: list[list[str]]) -> float:
    # Rough estimate (points per row) good enough for the bottom-of-page
    # heuristic above - exact row heights aren't available post-extraction.
    return len(rows) * 20.0
