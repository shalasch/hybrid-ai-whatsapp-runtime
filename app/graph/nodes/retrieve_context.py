import time
from app.graph.state import DecisionGraphState
from app.observability.logger import logger


def retrieve_context(state: DecisionGraphState) -> DecisionGraphState:
    _start = time.monotonic()
    ctx = state["runtime_context"]
    query = ctx.message.text
    warnings: list[str] = list(state.get("warnings", []))
    retrieval_mode = "vector"

    from app.config import settings
    embedding_provider = settings.rag_embedding_provider

    try:
        from app.rag.vector_store import retrieve
        docs = retrieve(query, top_k=settings.rag_top_k)
    except Exception as exc:
        logger.warning("vector_retrieval_failed_using_keyword_fallback", error=str(exc))
        warnings.append(f"vector_retrieval_failed:{type(exc).__name__}")
        retrieval_mode = "keyword_fallback"
        embedding_provider = "none"
        from app.rag.retriever import BasicRetriever
        docs = BasicRetriever().retrieve(query)

    duration_ms = round((time.monotonic() - _start) * 1000, 2)
    top_sources = [d.source for d in docs]
    top_scores = [round(d.score, 4) for d in docs]

    logger.info(
        "RETRIEVE_CONTEXT_COMPLETED",
        node_name="retrieve_context",
        retrieval_mode=retrieval_mode,
        retrieved_doc_count=len(docs),
        top_sources=top_sources,
        top_scores=top_scores,
        embedding_provider=embedding_provider,
        duration_ms=duration_ms,
        query_present=bool(query),
    )

    debug = {
        **state.get("debug", {}),
        "retrieve_context": {
            "retrieval_mode": retrieval_mode,
            "retrieved_doc_count": len(docs),
            "top_sources": top_sources,
            "top_scores": top_scores,
            "embedding_provider": embedding_provider,
            "duration_ms": duration_ms,
        },
    }

    return {**state, "retrieved_docs": docs, "warnings": warnings, "debug": debug}
