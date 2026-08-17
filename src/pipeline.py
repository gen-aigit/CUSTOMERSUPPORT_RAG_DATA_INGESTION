"""End-to-end orchestration shared by all three collections
(product_specs, technical_specs, refund_specs): load the PDF, parse it into
sections, chunk each section's text and tables, embed, and upsert into
whichever Weaviate collection the caller names. The loader/parser/chunkers
don't know or care which collection they're feeding - only the collection
name threads through, via ensure_collection().
"""

from pathlib import Path
from typing import Optional

from src.chunkers.table_chunker import table_to_chunk_texts
from src.chunkers.text_chunker import chunk_section_text
from src.embeddings.embedder import Embedder
from src.loaders.pdf_loader import load_pdf_elements
from src.models.schema import Chunk, Section
from src.parsers.section_parser import parse_sections
from src.utils.ids import build_chunk_id
from src.utils.logger import get_logger
from src.weaviate_store.client import weaviate_client
from src.weaviate_store.ingestor import ingest_chunks
from src.weaviate_store.schema import ensure_collection

logger = get_logger(__name__)


def run_ingestion(pdf_path: Path, collection_name: str) -> None:
    logger.info("Starting ingestion for %s -> collection '%s'", pdf_path, collection_name)

    elements = load_pdf_elements(pdf_path)
    sections = parse_sections(elements)
    if not sections:
        logger.warning("No sections were parsed from %s - nothing to ingest", pdf_path)
        return

    try:
        embedder = Embedder()
    except Exception:
        logger.exception("Could not initialize the embedding model - aborting")
        raise

    chunks = _build_chunks(sections, pdf_path.name, embedder.token_length)
    if not chunks:
        logger.warning("No chunks were produced from %s - nothing to ingest", pdf_path)
        return
    logger.info("Built %s chunk(s) from %s section(s)", len(chunks), len(sections))

    with weaviate_client() as client:
        collection = ensure_collection(client, collection_name)
        ingest_chunks(collection, chunks, embedder)

    logger.info("Finished ingestion for %s -> collection '%s'", pdf_path, collection_name)


def _build_chunks(sections: list[Section], file_name: str, token_length) -> list[Chunk]:
    chunks: list[Chunk] = []

    for section in sections:
        chunk_index = 0

        for raw_text in chunk_section_text(section, token_length):
            chunks.append(
                _make_chunk(
                    text=raw_text,
                    file_name=file_name,
                    page_no=section.page_no,
                    is_table=False,
                    section=section,
                    chunk_index=chunk_index,
                )
            )
            chunk_index += 1

        for table in section.tables:
            for raw_text in table_to_chunk_texts(table):
                chunks.append(
                    _make_chunk(
                        text=raw_text,
                        file_name=file_name,
                        page_no=table.page_no,
                        is_table=True,
                        section=section,
                        chunk_index=chunk_index,
                    )
                )
                chunk_index += 1

    return chunks


def _make_chunk(text: str, file_name: str, page_no: int, is_table: bool, section: Section, chunk_index: int) -> Chunk:
    return Chunk(
        chunk_id=build_chunk_id(file_name, page_no, section.section_title, chunk_index),
        chunk_text=_with_product_prefix(text, section.product_name),
        file_name=file_name,
        page_no=page_no,
        is_table=is_table,
        section_title=section.section_title,
        product_name=section.product_name,
    )


def _with_product_prefix(text: str, product_name: Optional[str]) -> str:
    """Embeds the product name into the chunk text itself, not just the
    metadata - pure semantic/keyword search over chunk_text should still
    find the right product even for a note that never restates its name
    inline (e.g. AuroraWatch Fit 3's "Reply-to-message... is Android-only"
    note never actually says "AuroraWatch Fit 3")."""

    if not product_name:
        return text
    return f"{product_name}: {text}"
