"""Creates a Weaviate collection (idempotent - reuses it if it already
exists) with the 8 properties settled on in the ingestion plan: chunk_text,
file_name, page_no, is_table, section_title, product_name, chunk_id,
ingested_at.

Vectorizer is explicitly "none": embeddings are computed client-side by
src/embeddings/embedder.py, not by a Weaviate built-in module.

This same 8-property shape is reused across all three collections
(product_specs, technical_specs, refund_specs) - they differ only in name
and source PDF(s), not in schema, so one function serves all three.
"""

import weaviate
import weaviate.classes.config as wc

from src.utils.logger import get_logger

logger = get_logger(__name__)


def ensure_collection(client: weaviate.WeaviateClient, name: str):
    if client.collections.exists(name):
        logger.info("Collection '%s' already exists - reusing it", name)
        return client.collections.get(name)

    logger.info("Creating collection '%s'", name)
    try:
        return client.collections.create(
            name=name,
            vectorizer_config=wc.Configure.Vectorizer.none(),
            properties=[
                wc.Property(name="chunk_text", data_type=wc.DataType.TEXT),
                wc.Property(name="file_name", data_type=wc.DataType.TEXT),
                wc.Property(name="page_no", data_type=wc.DataType.INT),
                wc.Property(name="is_table", data_type=wc.DataType.BOOL),
                wc.Property(name="section_title", data_type=wc.DataType.TEXT),
                wc.Property(name="product_name", data_type=wc.DataType.TEXT),
                wc.Property(name="chunk_id", data_type=wc.DataType.TEXT),
                wc.Property(name="ingested_at", data_type=wc.DataType.DATE),
            ],
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to create collection '{name}': {exc}") from exc
