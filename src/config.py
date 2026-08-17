"""Central settings, loaded once from .env."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    weaviate_http_host: str
    weaviate_http_port: int
    weaviate_grpc_host: str
    weaviate_grpc_port: int
    weaviate_api_key: Optional[str]

    embedding_model_name: str

    product_specs_collection: str
    technical_specs_collection: str
    refund_specs_collection: str

    chunk_size_tokens: int
    chunk_overlap_tokens: int

    log_file_path: Path
    log_level: str

    data_dir: Path
    ledger_file_path: Path


def _load_settings() -> Settings:
    return Settings(
        weaviate_http_host=os.getenv("WEAVIATE_HTTP_HOST", "localhost"),
        weaviate_http_port=int(os.getenv("WEAVIATE_HTTP_PORT", "8080")),
        weaviate_grpc_host=os.getenv("WEAVIATE_GRPC_HOST", "localhost"),
        weaviate_grpc_port=int(os.getenv("WEAVIATE_GRPC_PORT", "50051")),
        weaviate_api_key=os.getenv("WEAVIATE_API_KEY") or None,
        embedding_model_name=os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-base-en-v1.5"),
        product_specs_collection=os.getenv("PRODUCT_SPECS_COLLECTION", "product_specs"),
        technical_specs_collection=os.getenv("TECHNICAL_SPECS_COLLECTION", "technical_specs"),
        refund_specs_collection=os.getenv("REFUND_SPECS_COLLECTION", "refund_specs"),
        chunk_size_tokens=int(os.getenv("CHUNK_SIZE_TOKENS", "300")),
        chunk_overlap_tokens=int(os.getenv("CHUNK_OVERLAP_TOKENS", "40")),
        log_file_path=PROJECT_ROOT / os.getenv("LOG_FILE_PATH", "logs/ingestion.log"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        data_dir=PROJECT_ROOT / os.getenv("DATA_DIR", "data"),
        ledger_file_path=PROJECT_ROOT / os.getenv("LEDGER_FILE_PATH", "logs/ingestion_ledger.json"),
    )


settings = _load_settings()
