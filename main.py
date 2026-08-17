"""CLI entrypoint for the product_specs ingestion pipeline.

Usage:
    python main.py                                    # ingests every PDF under data/product_specs/
    python main.py --file data/product_specs/x.pdf     # ingests one specific PDF
"""

import argparse
import sys
from pathlib import Path

from src.config import settings
from src.pipeline import run_product_specs_ingestion
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _discover_pdfs() -> list[Path]:
    folder = settings.data_dir / "product_specs"
    return sorted(folder.glob("*.pdf"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest product_specs PDF(s) into Weaviate")
    parser.add_argument("--file", type=Path, help="Path to a single PDF to ingest")
    args = parser.parse_args()

    pdf_paths = [args.file] if args.file else _discover_pdfs()
    if not pdf_paths:
        logger.error(
            "No PDF found. Pass --file <path>, or place a PDF under %s",
            settings.data_dir / "product_specs",
        )
        return 1

    exit_code = 0
    for pdf_path in pdf_paths:
        try:
            run_product_specs_ingestion(pdf_path)
        except Exception:
            logger.exception("Ingestion failed for %s", pdf_path)
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
