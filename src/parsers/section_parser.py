"""Groups the flat, ordered element stream from the PDF loader into
Sections: numbered heading -> everything until the next numbered heading.

All three source documents number their sections the same way
("1. AuroraBuds Pro 2 - ...", "1. Standard Return Window"), so one regex
covers all of them. Content before the first numbered heading (the
title/subtitle/scope paragraph at the top of the doc) becomes its own
"Document Overview" section instead of being dropped, since that text often
explains what the document does and doesn't cover.
"""

import re
from typing import Optional

from src.loaders.pdf_loader import PageElement
from src.models.schema import Section, TableBlock
from src.utils.logger import get_logger

logger = get_logger(__name__)

_HEADING_RE = re.compile(r"^\s*(\d+)\.\s+(.+?)\s*$")
_DASH_SPLIT_RE = re.compile(r"\s+[—–-]\s+")  # em dash, en dash, hyphen


def parse_sections(elements: list[PageElement]) -> list[Section]:
    if not elements:
        logger.warning("No elements to parse into sections - returning empty section list")
        return []

    sections: list[Section] = []
    current = Section(
        section_number=0,
        section_title="Document Overview",
        product_name=None,
        page_no=elements[0].page_no,
    )

    for element in elements:
        if element.kind == "table":
            current.tables.append(TableBlock(rows=element.rows, page_no=element.page_no))
            continue

        heading_match = _HEADING_RE.match(element.text or "")
        if heading_match:
            _flush(sections, current)
            number = int(heading_match.group(1))
            title = heading_match.group(2).strip()
            current = Section(
                section_number=number,
                section_title=title,
                product_name=_extract_product_name(title),
                page_no=element.page_no,
            )
        else:
            if element.text and element.text.strip():
                current.text_parts.append(element.text.strip())

    _flush(sections, current)

    logger.info("Parsed %s sections", len(sections))
    return sections


def _flush(sections: list[Section], section: Section) -> None:
    if section.text_parts or section.tables:
        sections.append(section)


def _extract_product_name(section_title: str) -> Optional[str]:
    """"AuroraBuds Pro 2 - True Wireless Earbuds" -> "AuroraBuds Pro 2".
    Section titles with no dash (e.g. "Standard Return Window") yield None,
    which is the correct answer for documents that aren't product-organized."""

    parts = _DASH_SPLIT_RE.split(section_title, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip()
    return None
