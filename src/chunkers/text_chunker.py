"""Splits one section's narrative text into token-sized chunks.

Called once per Section, never across sections - that's what keeps a chunk
from ever mixing content from two unrelated products/sections. Sizing is
done in tokens (via the embedding model's own tokenizer, injected as
`token_length`) rather than raw characters, since the embedding model has a
hard token limit and character counts don't reliably predict token counts.
"""

from typing import Callable

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import settings
from src.models.schema import Section
from src.utils.logger import get_logger

logger = get_logger(__name__)

_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def chunk_section_text(section: Section, token_length: Callable[[str], int]) -> list[str]:
    text = "\n\n".join(part for part in section.text_parts if part.strip())
    if not text.strip():
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size_tokens,
        chunk_overlap=settings.chunk_overlap_tokens,
        length_function=token_length,
        separators=_SEPARATORS,
    )
    chunks = [c.strip() for c in splitter.split_text(text) if c.strip()]
    print("Chunks data:",chunks)
    logger.debug(
        "Section %s '%s': narrative text -> %s chunk(s)",
        section.section_number,
        section.section_title,
        len(chunks),
    )
    return chunks
