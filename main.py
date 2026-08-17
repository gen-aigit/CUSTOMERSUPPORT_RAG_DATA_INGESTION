"""CLI entrypoint for ingestion across all three collections: product_specs,
technical_specs, refund_specs. Each has its own data/<name>/ subfolder of
source PDFs but runs through the same pipeline (src/pipeline.py).

Usage:
    python main.py                                                     # ingests every PDF under every collection's data/<name>/ folder
    python main.py --collection technical_specs                        # ingests only technical_specs' PDFs
    python main.py --file data/refund_specs/x.pdf --collection refund_specs   # ingests one specific PDF into one collection
"""

import argparse
import sys
from pathlib import Path

from src.config import settings
from src.pipeline import run_ingestion
from src.utils.logger import get_logger

logger = get_logger(__name__)

_COLLECTIONS = {
    "product_specs": settings.product_specs_collection,
    "technical_specs": settings.technical_specs_collection,
    "refund_specs": settings.refund_specs_collection,
}


def _discover_pdfs(subfolder: str) -> list[Path]:
    folder = settings.data_dir / subfolder
    return sorted(folder.glob("*.pdf"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest PDF(s) into a Weaviate collection")
    parser.add_argument("--file", type=Path, help="Path to a single PDF to ingest (requires --collection)")
    parser.add_argument(
        "--collection",
        choices=sorted(_COLLECTIONS),
        help="Limit ingestion to one collection's data subfolder (default: all three)",
    )
    args = parser.parse_args()

    if args.file and not args.collection:
        logger.error("--file requires --collection so the pipeline knows which collection to ingest into")
        return 1

    subfolders = [args.collection] if args.collection else sorted(_COLLECTIONS)

    exit_code = 0
    any_found = False
    for subfolder in subfolders:
        collection_name = _COLLECTIONS[subfolder]
        pdf_paths = [args.file] if args.file else _discover_pdfs(subfolder)
        if not pdf_paths:
            logger.warning(
                "No PDF found for '%s'. Place a PDF under %s",
                subfolder,
                settings.data_dir / subfolder,
            )
            continue

        any_found = True
        for pdf_path in pdf_paths:
            try:
                run_ingestion(pdf_path, collection_name)
            except Exception:
                logger.exception("Ingestion failed for %s (collection '%s')", pdf_path, collection_name)
                exit_code = 1

    if not any_found:
        logger.error("No PDFs found under any collection's data subfolder in %s", settings.data_dir)
        return 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
