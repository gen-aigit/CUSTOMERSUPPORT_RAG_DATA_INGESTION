"""Standalone retrieval smoke test - run against an already-ingested
product_specs collection to sanity-check chunking/embedding quality
before any retrieval pipeline is built on top of it.

For each query in golden_dataset.GOLDEN_QUERIES: embeds the query the same
way a real retrieval pipeline would (Embedder.embed_query, which applies
the BGE asymmetric-retrieval instruction prefix), runs a near_vector
search, and checks whether a chunk from the expected product - containing
the expected keyword - shows up in the top-k results.

Usage (from project root, venv activated, Weaviate running, PDF already
ingested via `python main.py`):
    python -m src.tests.test_retrieval
"""

from weaviate.classes.query import MetadataQuery

from src.embeddings.embedder import Embedder
from src.tests.golden_dataset import GOLDEN_QUERIES, GoldenQuery
from src.weaviate_store.client import weaviate_client
from src.weaviate_store.schema import ensure_product_specs_collection

_TOP_K = 5


def _print_result(gq: GoldenQuery, match_rank, match_certainty, first_result) -> None:
    status = "PASS" if match_rank else "FAIL"
    print(f"[{status}] {gq.query}")
    print(f"    expected: product={gq.expected_product!r} keyword={gq.expected_keyword!r}")
    if match_rank:
        print(f"    found at rank {match_rank}/{_TOP_K}, certainty={match_certainty:.3f}")
    elif first_result is not None:
        print(
            f"    not found in top {_TOP_K} - top result was "
            f"product={first_result.properties.get('product_name')!r} "
            f"section={first_result.properties.get('section_title')!r}"
        )
    else:
        print("    not found - query returned no results at all")
    print()


def run() -> None:
    embedder = Embedder()

    with weaviate_client() as client:
        collection = ensure_product_specs_collection(client)

        passed = 0
        for gq in GOLDEN_QUERIES:
            vector = embedder.embed_query(gq.query)
            results = collection.query.near_vector(
                near_vector=vector,
                limit=_TOP_K,
                return_metadata=MetadataQuery(certainty=True),
            )

            match_rank, match_certainty = None, None
            for rank, obj in enumerate(results.objects, start=1):
                chunk_text = (obj.properties.get("chunk_text") or "").lower()
                if (
                    obj.properties.get("product_name") == gq.expected_product
                    and gq.expected_keyword.lower() in chunk_text
                ):
                    match_rank, match_certainty = rank, obj.metadata.certainty
                    break

            _print_result(gq, match_rank, match_certainty, results.objects[0] if results.objects else None)
            passed += match_rank is not None

        total = len(GOLDEN_QUERIES)
        print(f"Recall@{_TOP_K}: {passed}/{total} ({passed / total:.0%})")


if __name__ == "__main__":
    run()
