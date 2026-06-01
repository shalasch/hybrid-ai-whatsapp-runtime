from __future__ import annotations

from pathlib import Path

from app.rag.retriever import RetrievedDocument
from app.rag.embedding import make_embedding_function
from app.observability.logger import logger

# Absolute project root — reliable regardless of CWD.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Module-level collection cache. Set to None to force re-initialization.
# Override _chroma_path and _make_embedding_function in tests via monkeypatch.
_collection = None
_chroma_path: str | None = None  # test override; None means "use settings"

# Monkeypatchable reference to the embedding factory — tests replace this
# with ONNXMiniLM_L6_V2 to avoid real API calls.
_make_embedding_function = make_embedding_function


def _get_chroma_path() -> str:
    if _chroma_path is not None:
        return _chroma_path
    from app.config import settings
    return settings.chroma_path


def _try_ingest(collection, kb_dir: Path, client, label: str) -> int:
    from app.rag.ingest import ingest_into_collection
    n = ingest_into_collection(collection, kb_dir)
    logger.info("RAG_AUTO_INGEST_COMPLETE", chunks_ingested=n, provider=label)
    return n


def get_or_create_collection():
    global _collection
    if _collection is not None:
        return _collection

    import chromadb
    from app.config import settings

    path = _get_chroma_path()
    Path(path).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=path)

    ef = _make_embedding_function()
    _collection = client.get_or_create_collection(
        name="knowledge_base",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    if _collection.count() == 0:
        kb_dir = _PROJECT_ROOT / "knowledge_base"
        if not kb_dir.exists():
            logger.warning("RAG_KB_DIR_NOT_FOUND", kb_dir=str(kb_dir))
            return _collection

        provider = settings.rag_embedding_provider
        logger.info("RAG_AUTO_INGEST_START", kb_dir=str(kb_dir), provider=provider)

        try:
            _try_ingest(_collection, kb_dir, client, provider)
        except Exception as exc:
            logger.error("RAG_AUTO_INGEST_FAILED", error=str(exc), provider=provider)

            if provider == "openai":
                # OpenAI embedding call failed (quota / rate limit / network).
                # Recreate the empty collection with ONNX and retry.
                logger.warning(
                    "RAG_EMBEDDING_FALLBACK_TO_ONNX",
                    reason=type(exc).__name__,
                    hint="Set RAG_EMBEDDING_PROVIDER=onnx to avoid this fallback",
                )
                from app.rag.embedding import onnx_embedding_function
                try:
                    client.delete_collection("knowledge_base")
                except Exception:
                    pass
                _collection = client.get_or_create_collection(
                    name="knowledge_base",
                    embedding_function=onnx_embedding_function(),
                    metadata={"hnsw:space": "cosine"},
                )
                try:
                    _try_ingest(_collection, kb_dir, client, "onnx_fallback")
                except Exception as exc2:
                    logger.error("RAG_ONNX_FALLBACK_INGEST_FAILED", error=str(exc2))

    return _collection


def retrieve(query: str | None, top_k: int = 3) -> list[RetrievedDocument]:
    if not query:
        return []

    collection = get_or_create_collection()
    count = collection.count()
    if count == 0:
        logger.warning("RAG_COLLECTION_EMPTY_returning_no_docs")
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, count),
        include=["documents", "metadatas", "distances"],
    )

    docs: list[RetrievedDocument] = []
    for content, metadata, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        score = round(max(0.0, 1.0 - distance), 4)
        docs.append(
            RetrievedDocument(
                source=metadata.get("source", "unknown"),
                content=content,
                score=score,
            )
        )
    return docs
