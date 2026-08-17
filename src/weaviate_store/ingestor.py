"""Embeds and upserts chunks into a Weaviate collection: batched inserts
(not one-by-one), retried on individual failure, and tracked in a local
JSON ledger so a failed run can resume without re-embedding/re-inserting
chunks that already succeeded - embedding is the expensive step here, worth
not repeating.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config import settings
from src.embeddings.embedder import Embedder
from src.models.schema import Chunk
from src.utils.logger import get_logger

logger = get_logger(__name__)

_FAILURE_RATE_ABORT_THRESHOLD = 0.5


class Ledger:
    """Tracks which chunk_ids have already been ingested successfully."""

    def __init__(self, path: Path):
        self.path = path
        self._done: set[str] = set()
        if path.exists():
            try:
                self._done = set(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                logger.warning("Ledger file at %s is unreadable - starting a fresh ledger", path)

    def is_done(self, chunk_id: str) -> bool:
        return chunk_id in self._done

    def mark_done(self, chunk_id: str) -> None:
        self._done.add(chunk_id)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(sorted(self._done)), encoding="utf-8")


def ingest_chunks(collection, chunks: list[Chunk], embedder: Embedder) -> None:
    if not chunks:
        logger.warning("No chunks to ingest")
        return
    # explicitly printing chunk
    # for chunk in chunks:
    #     logger.info(
    #                     "ChunkID %s | PAGE=%s | SECTION='%s' | PRODUCT=%s | is_table=%s | chars=%s | CHUNK_TEXT=%r",
    #                     chunk.chunk_id,
    #                     chunk.page_no,
    #                     chunk.section_title,
    #                     chunk.product_name,
    #                     chunk.is_table,
    #                     len(chunk.chunk_text),
    #                     chunk.chunk_text,
    #                 )

      
    ledger = Ledger(settings.ledger_file_path)
    pending = [c for c in chunks if not ledger.is_done(c.chunk_id)]
    skipped = len(chunks) - len(pending)
    if skipped:
        logger.info("Skipping %s chunk(s) already ingested per the ledger", skipped)
    if not pending:
        logger.info("Nothing new to ingest")
        return

    logger.info("Embedding %s chunk(s)", len(pending))
    try:
        vectors = embedder.embed_documents([c.chunk_text for c in pending])
    except Exception:
        logger.exception("Embedding failed for this batch - aborting ingestion, nothing was written")
        raise

    ingested_at = datetime.now(timezone.utc).isoformat()

    logger.info("Inserting %s chunk(s) into '%s' as a batch", len(pending), collection.name)
    with collection.batch.dynamic() as batch:
        for chunk, vector in zip(pending, vectors):
            logger.info(
                "Chunk %s | page=%s | section='%s' | product=%s | is_table=%s | chars=%s | text=%r",
                chunk.chunk_id,
                chunk.page_no,
                chunk.section_title,
                chunk.product_name,
                chunk.is_table,
                len(chunk.chunk_text),
                chunk.chunk_text,
            )
            batch.add_object(
                properties=_build_properties(chunk, ingested_at),
                uuid=chunk.chunk_id,
                vector=vector,
            )

    failed_ids = _extract_failed_ids(collection)
    if failed_ids:
        logger.warning("%s chunk(s) failed in the batch insert - retrying individually", len(failed_ids))
        vectors_by_id = {c.chunk_id: v for c, v in zip(pending, vectors)}
        chunks_by_id = {c.chunk_id: c for c in pending}
        still_failed: set[str] = set()
        for chunk_id in failed_ids:
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None:
                still_failed.add(chunk_id)
                continue
            if not _retry_single_insert(collection, chunk, vectors_by_id[chunk_id], ingested_at):
                still_failed.add(chunk_id)
        failed_ids = still_failed

    failure_rate = len(failed_ids) / len(pending)
    if failure_rate > _FAILURE_RATE_ABORT_THRESHOLD:
        for chunk in pending:
            if chunk.chunk_id not in failed_ids:
                ledger.mark_done(chunk.chunk_id)
        ledger.save()
        raise RuntimeError(
            f"{len(failed_ids)}/{len(pending)} chunks failed to ingest "
            f"(over the {_FAILURE_RATE_ABORT_THRESHOLD:.0%} abort threshold) - "
            "stopping rather than continuing against a possibly-unhealthy "
            "Weaviate instance. Already-succeeded chunks are saved to the "
            "ledger, so re-running will only retry what's left."
        )

    for chunk in pending:
        if chunk.chunk_id not in failed_ids:
            ledger.mark_done(chunk.chunk_id)
    ledger.save()

    logger.info(
        "Ingestion finished: %s succeeded, %s failed, %s skipped (already in ledger)",
        len(pending) - len(failed_ids),
        len(failed_ids),
        skipped,
    )


def _build_properties(chunk: Chunk, ingested_at: str) -> dict:
    return {
        "chunk_text": chunk.chunk_text,
        "file_name": chunk.file_name,
        "page_no": chunk.page_no,
        "is_table": chunk.is_table,
        "section_title": chunk.section_title,
        "product_name": chunk.product_name,
        "chunk_id": chunk.chunk_id,
        "ingested_at": ingested_at,
    }


def _extract_failed_ids(collection) -> set[str]:
    """collection.batch.failed_objects holds whatever the batch context
    couldn't insert. Extracting the UUID back out is wrapped defensively
    since the exact attribute name has moved between weaviate-client
    versions - if it can't be found, the object is still counted as failed,
    just without being individually retried."""

    failed_ids: set[str] = set()
    try:
        failed_objects = list(collection.batch.failed_objects)
    except Exception:
        logger.exception("Could not read batch.failed_objects from the client")
        return failed_ids

    for failed in failed_objects:
        uuid = _uuid_from_failed_object(failed)
        if uuid:
            failed_ids.add(uuid)
        else:
            logger.error("A batch object failed and its chunk_id could not be recovered: %s", failed)
    return failed_ids


def _uuid_from_failed_object(failed) -> Optional[str]:
    for path in ("object_.uuid", "original_uuid", "uuid"):
        obj = failed
        try:
            for attr in path.split("."):
                obj = getattr(obj, attr)
            if obj:
                return str(obj)
        except AttributeError:
            continue
    return None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _insert_one(collection, chunk: Chunk, vector: list[float], ingested_at: str) -> None:
    collection.data.insert(
        properties=_build_properties(chunk, ingested_at),
        uuid=chunk.chunk_id,
        vector=vector,
    )


def _retry_single_insert(collection, chunk: Chunk, vector: list[float], ingested_at: str) -> bool:
    try:
        _insert_one(collection, chunk, vector, ingested_at)
        return True
    except Exception:
        logger.exception("Retries exhausted for chunk %s - giving up on it for this run", chunk.chunk_id)
        return False
