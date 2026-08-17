"""Embedding generation via a local Hugging Face model (BAAI/bge-base-en-v1.5,
768-dim by default). Also exposes a token-counting helper so the text
chunker can size chunks against this exact model's token limit instead of
guessing from raw character counts.
"""

from typing import Optional

from langchain_huggingface import HuggingFaceEmbeddings

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# BGE models are trained for asymmetric retrieval: queries should carry this
# instruction prefix, stored documents should not.
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class Embedder:
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.embedding_model_name
        logger.info("Loading embedding model '%s' (downloads on first run, then cached)", self.model_name)
        try:
            self._embeddings = HuggingFaceEmbeddings(model_name=self.model_name)
        except Exception as exc:
            raise RuntimeError(
                f"Could not load embedding model '{self.model_name}'. "
                "Check that sentence-transformers/torch installed correctly "
                "for this Python version and that there's network access to "
                "download the model on first run."
            ) from exc
        self._tokenizer = self._resolve_tokenizer()

    def _resolve_tokenizer(self):
        try:
            return self._embeddings.client.tokenizer
        except AttributeError:
            logger.warning(
                "Could not access the underlying tokenizer for '%s'; "
                "falling back to a word-count approximation for chunk sizing",
                self.model_name,
            )
            return None

    def token_length(self, text: str) -> int:
        if self._tokenizer is not None:
            return len(self._tokenizer.encode(text, add_special_tokens=False))
        return len(text.split())

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embeddings.embed_query(QUERY_INSTRUCTION + text)
