"""
Shared embedding function factory for ChromaDB ingestion and retrieval.

Provider is controlled by RAG_EMBEDDING_PROVIDER:

  onnx   (default) — ONNXMiniLM_L6_V2, fully local, no API key required.
  openai            — text-embedding-3-small via OpenAI API.
                      Falls back to ONNX if OPENAI_API_KEY is not set.
                      Callers should catch exceptions and retry with ONNX
                      if the API call itself fails (quota / rate limit).
"""
from __future__ import annotations


def make_embedding_function():
    """Return the configured ChromaDB EmbeddingFunction instance."""
    from chromadb.utils import embedding_functions
    from app.config import settings

    if settings.rag_embedding_provider == "openai":
        if settings.openai_api_key:
            return embedding_functions.OpenAIEmbeddingFunction(
                api_key=settings.openai_api_key,
                model_name=settings.openai_embedding_model,
            )
        # Key not set — fall back silently; logged at ingest/retrieval site.
        from app.observability.logger import logger
        logger.warning(
            "RAG_OPENAI_EF_NO_KEY_falling_back_to_onnx",
            hint="Set OPENAI_API_KEY or use RAG_EMBEDDING_PROVIDER=onnx",
        )

    return embedding_functions.ONNXMiniLM_L6_V2()


def onnx_embedding_function():
    """Return an ONNX EmbeddingFunction regardless of provider config."""
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
    return ONNXMiniLM_L6_V2()
