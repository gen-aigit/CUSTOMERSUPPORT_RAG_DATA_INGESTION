"""Deterministic chunk IDs.

A chunk has no natural unique field of its own (unlike, say, a movie record
with a ready-made `movie["id"]`), so we build one by joining the handful of
fields that together identify exactly one chunk, then hash that string the
same way `generate_uuid5(movie["id"])` would. Re-running the pipeline on an
unchanged PDF reproduces the same IDs, so Weaviate updates existing objects
instead of duplicating them.
"""

from weaviate.util import generate_uuid5


def build_chunk_id(file_name: str, page_no: int, section_title: str, chunk_index: int) -> str:
    key = f"{file_name}_{page_no}_{section_title}_{chunk_index}"
    return generate_uuid5(key)
