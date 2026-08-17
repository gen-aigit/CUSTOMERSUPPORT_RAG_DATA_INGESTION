"""Weaviate connection handling (local Docker instance)."""

from contextlib import contextmanager

import weaviate
from weaviate.auth import AuthApiKey
from weaviate.classes.init import AdditionalConfig, Timeout

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


@contextmanager
def weaviate_client():
    """Connects to the local Weaviate instance and fails fast (with a clear
    message) if it isn't up, instead of letting later calls fail with an
    opaque connection error."""

    auth = AuthApiKey(settings.weaviate_api_key) if settings.weaviate_api_key else None

    try:
        client = weaviate.connect_to_local(
            host=settings.weaviate_http_host,
            port=settings.weaviate_http_port,
            grpc_port=settings.weaviate_grpc_port,
            auth_credentials=auth,
            additional_config=AdditionalConfig(timeout=Timeout(init=30, query=60, insert=120)),
        )
    except Exception as exc:
        raise ConnectionError(
            f"Could not connect to Weaviate at "
            f"{settings.weaviate_http_host}:{settings.weaviate_http_port} "
            "(gRPC port "
            f"{settings.weaviate_grpc_port}). Is the local Docker instance running?"
        ) from exc

    try:
        if not client.is_ready():
            raise ConnectionError(
                f"Weaviate at {settings.weaviate_http_host}:{settings.weaviate_http_port} "
                "responded but is not ready. Is the local Docker instance still starting up?"
            )
        logger.info(
            "Connected to Weaviate at %s:%s (gRPC %s)",
            settings.weaviate_http_host,
            settings.weaviate_http_port,
            settings.weaviate_grpc_port,
        )
        yield client
    finally:
        client.close()
