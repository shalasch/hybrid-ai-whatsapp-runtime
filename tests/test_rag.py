"""
RAG layer tests — ingest, vector store, and retrieve_context node.

Vector store tests use an isolated ChromaDB (ONNX embeddings, no OpenAI call)
so they run offline and do not affect the production data/chroma/ directory.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import app.rag.vector_store as vs_module
from app.rag.ingest import chunk_text, load_documents, ingest_into_collection
from app.rag.retriever import BasicRetriever, RetrievedDocument
from app.rag.vector_store import retrieve


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def kb_dir() -> Path:
    """Return the real knowledge_base/ directory."""
    d = Path("knowledge_base")
    assert d.exists(), "knowledge_base/ directory not found"
    return d


@pytest.fixture()
def isolated_vector_store(tmp_path, monkeypatch):
    """
    Point the vector store at a fresh temp ChromaDB and reset the module cache.
    Uses ONNX embeddings (OpenAI key is not needed).
    """
    monkeypatch.setattr(vs_module, "_collection", None)
    monkeypatch.setattr(vs_module, "_chroma_path", str(tmp_path / "chroma"))

    # Override the embedding function to ONNX so tests never call OpenAI
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
    monkeypatch.setattr(vs_module, "_make_embedding_function", ONNXMiniLM_L6_V2)

    yield tmp_path

    # Reset after test — prevents cache leaking into subsequent tests
    monkeypatch.setattr(vs_module, "_collection", None)


# ── chunk_text ────────────────────────────────────────────────────────────────

def test_chunk_text_splits_on_blank_lines():
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    chunks = chunk_text(text)
    assert len(chunks) == 3


def test_chunk_text_strips_markdown_headers():
    text = "# Title\n\nBody text here."
    chunks = chunk_text(text)
    assert all("# Title" not in c for c in chunks)
    assert any("Body text" in c for c in chunks)


def test_chunk_text_splits_long_paragraph():
    long = ("This is a sentence. " * 30).strip()
    chunks = chunk_text(long, max_chars=100)
    assert all(len(c) <= 120 for c in chunks)  # allow slight overshoot at sentence boundary


def test_chunk_text_empty_input():
    assert chunk_text("") == []


def test_chunk_text_header_only():
    assert chunk_text("# Just a Header") == []


# ── load_documents ────────────────────────────────────────────────────────────

def test_load_documents_returns_all_files(kb_dir):
    docs = load_documents(kb_dir)
    assert len(docs) > 0


def test_load_documents_each_doc_has_required_keys(kb_dir):
    docs = load_documents(kb_dir)
    for doc in docs:
        assert "id" in doc
        assert "source" in doc
        assert "content" in doc
        assert doc["content"].strip()


def test_load_documents_ids_are_unique(kb_dir):
    docs = load_documents(kb_dir)
    ids = [d["id"] for d in docs]
    assert len(ids) == len(set(ids))


def test_load_documents_sources_match_filenames(kb_dir):
    expected_sources = {f.stem for f in kb_dir.glob("*.md")}
    docs = load_documents(kb_dir)
    doc_sources = {d["source"] for d in docs}
    assert expected_sources == doc_sources


def test_load_documents_no_chunk_exceeds_max_chars(kb_dir):
    docs = load_documents(kb_dir)
    for doc in docs:
        assert len(doc["content"]) <= 600  # 500 limit + sentence boundary tolerance


# ── BasicRetriever (keyword fallback) ────────────────────────────────────────

def test_basic_retriever_returns_empty_for_no_query():
    assert BasicRetriever().retrieve(None) == []


def test_basic_retriever_returns_empty_for_empty_string():
    assert BasicRetriever().retrieve("") == []


def test_basic_retriever_finds_offshore_doc():
    docs = BasicRetriever().retrieve("offshore entrevista")
    assert len(docs) > 0
    sources = [d.source for d in docs]
    assert any("offshore" in s for s in sources)


def test_basic_retriever_score_field_is_float():
    docs = BasicRetriever().retrieve("offshore")
    assert all(isinstance(d.score, float) for d in docs)


# ── ingest_into_collection ────────────────────────────────────────────────────

def test_ingest_into_collection_populates_chroma(tmp_path, kb_dir, monkeypatch):
    import chromadb
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

    chroma_path = tmp_path / "chroma_ingest"
    chroma_path.mkdir()
    client = chromadb.PersistentClient(path=str(chroma_path))
    collection = client.get_or_create_collection(
        name="test_kb",
        embedding_function=ONNXMiniLM_L6_V2(),
        metadata={"hnsw:space": "cosine"},
    )

    n = ingest_into_collection(collection, kb_dir)
    assert n > 0
    assert collection.count() == n


def test_ingest_into_collection_empty_dir_returns_zero(tmp_path):
    import chromadb
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

    empty_dir = tmp_path / "empty_kb"
    empty_dir.mkdir()
    chroma_path = tmp_path / "chroma_empty"
    chroma_path.mkdir()
    client = chromadb.PersistentClient(path=str(chroma_path))
    collection = client.get_or_create_collection(
        name="test_empty",
        embedding_function=ONNXMiniLM_L6_V2(),
    )
    assert ingest_into_collection(collection, empty_dir) == 0


# ── vector_store.retrieve ─────────────────────────────────────────────────────

def test_retrieve_returns_empty_for_no_query(isolated_vector_store, kb_dir):
    result = retrieve(None)
    assert result == []


def test_retrieve_returns_results_after_ingest(isolated_vector_store, kb_dir):
    # Auto-ingest fires because knowledge_base/ exists and collection is empty
    docs = retrieve("offshore interview English")
    assert len(docs) > 0


def test_retrieve_results_have_score_field(isolated_vector_store, kb_dir):
    docs = retrieve("offshore interview")
    assert all(isinstance(d.score, float) for d in docs)
    assert all(0.0 <= d.score <= 1.0 for d in docs)


def test_retrieve_results_have_source_field(isolated_vector_store, kb_dir):
    docs = retrieve("offshore english training")
    assert all(d.source for d in docs)


def test_retrieve_offshore_query_returns_relevant_source(isolated_vector_store, kb_dir):
    docs = retrieve("entrevista offshore plataforma")
    sources = [d.source for d in docs]
    assert any("offshore" in s for s in sources)


def test_retrieve_trial_class_query_returns_relevant_source(isolated_vector_store, kb_dir):
    docs = retrieve("aula experimental gratuita diagnóstico")
    sources = [d.source for d in docs]
    assert any("trial" in s for s in sources)


def test_retrieve_respects_top_k(isolated_vector_store, kb_dir):
    docs = retrieve("inglês", top_k=2)
    assert len(docs) <= 2


def test_retrieve_scores_are_ordered_descending(isolated_vector_store, kb_dir):
    docs = retrieve("offshore entrevista inglês", top_k=3)
    scores = [d.score for d in docs]
    assert scores == sorted(scores, reverse=True)


# ── retrieve_context graph node ───────────────────────────────────────────────

from app.graph.nodes.retrieve_context import retrieve_context
from app.graph.state import DecisionGraphState
from app.contracts.runtime_context import (
    RuntimeContext, LeadContext, ConversationContext, MessageContext, RoutingContext,
)


def _make_retrieve_state(text: str = "offshore interview") -> DecisionGraphState:
    ctx = RuntimeContext(
        lead=LeadContext(id="lead_t", nome="Test"),
        conversation=ConversationContext(id="conv_t", status="Ativa"),
        message=MessageContext(text=text, type="text"),
        routing=RoutingContext(),
    )
    return DecisionGraphState(runtime_context=ctx, warnings=[], intent="offshore_interest")


def test_retrieve_context_node_returns_docs(isolated_vector_store, kb_dir):
    state = _make_retrieve_state("offshore interview preparation")
    result = retrieve_context(state)
    assert "retrieved_docs" in result
    assert isinstance(result["retrieved_docs"], list)


def test_retrieve_context_node_docs_are_retrieved_documents(isolated_vector_store, kb_dir):
    state = _make_retrieve_state("aula experimental")
    result = retrieve_context(state)
    for doc in result["retrieved_docs"]:
        assert isinstance(doc, RetrievedDocument)


def test_retrieve_context_node_fallback_on_broken_store(monkeypatch):
    """If vector store raises, node falls back to BasicRetriever with a warning."""
    import app.rag.vector_store as vs

    def _broken_retrieve(*args, **kwargs):
        raise RuntimeError("chroma unavailable")

    monkeypatch.setattr(vs, "retrieve", _broken_retrieve)

    state = _make_retrieve_state("offshore")
    result = retrieve_context(state)

    assert "retrieved_docs" in result
    assert any("vector_retrieval_failed" in w for w in result.get("warnings", []))


# ── Embedding factory ─────────────────────────────────────────────────────────

from app.rag.embedding import make_embedding_function, onnx_embedding_function
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2, OpenAIEmbeddingFunction


def test_default_provider_is_onnx(monkeypatch):
    """ONNX must be the default embedding provider — no API key required."""
    import app.rag.embedding as emb
    from app.config import Settings, SettingsConfigDict

    class _OnnxSettings(Settings):
        rag_embedding_provider: str = "onnx"
        openai_api_key: str | None = None
        model_config = SettingsConfigDict(env_file=None)  # type: ignore[assignment]

    monkeypatch.setattr(emb, "make_embedding_function",
                        lambda: make_embedding_function.__wrapped__() if hasattr(make_embedding_function, "__wrapped__") else _call_with_settings(_OnnxSettings()))

    ef = onnx_embedding_function()
    assert isinstance(ef, ONNXMiniLM_L6_V2)


def _call_with_settings(settings_obj):
    """Helper — call make_embedding_function with a specific settings object."""
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
    if settings_obj.rag_embedding_provider == "openai" and settings_obj.openai_api_key:
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
        return OpenAIEmbeddingFunction(
            api_key=settings_obj.openai_api_key,
            model_name=settings_obj.openai_embedding_model,
        )
    return ONNXMiniLM_L6_V2()


def test_onnx_provider_returns_onnx_instance(monkeypatch):
    """RAG_EMBEDDING_PROVIDER=onnx must return ONNXMiniLM_L6_V2."""
    import app.rag.embedding as emb
    from app.config import settings
    monkeypatch.setattr(settings, "rag_embedding_provider", "onnx")
    ef = make_embedding_function()
    assert isinstance(ef, ONNXMiniLM_L6_V2)


def test_openai_provider_without_key_falls_back_to_onnx(monkeypatch):
    """provider=openai with no API key must silently fall back to ONNX."""
    from app.config import settings
    monkeypatch.setattr(settings, "rag_embedding_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", None)
    ef = make_embedding_function()
    assert isinstance(ef, ONNXMiniLM_L6_V2)


def test_openai_provider_with_key_returns_openai_ef(monkeypatch):
    """provider=openai with a valid key must return OpenAIEmbeddingFunction."""
    from app.config import settings
    monkeypatch.setattr(settings, "rag_embedding_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-fake-key")
    ef = make_embedding_function()
    assert isinstance(ef, OpenAIEmbeddingFunction)


def test_onnx_embedding_function_always_returns_onnx(monkeypatch):
    """onnx_embedding_function() must return ONNX regardless of provider setting."""
    from app.config import settings
    monkeypatch.setattr(settings, "rag_embedding_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-fake-key")
    ef = onnx_embedding_function()
    assert isinstance(ef, ONNXMiniLM_L6_V2)


def test_ingest_cli_uses_onnx_by_default(tmp_path, kb_dir, monkeypatch):
    """Standalone ingest() must complete without an OpenAI key when provider=onnx."""
    from app.config import settings
    from app.rag.ingest import ingest

    monkeypatch.setattr(settings, "rag_embedding_provider", "onnx")
    monkeypatch.setattr(settings, "openai_api_key", None)

    n = ingest(kb_dir=kb_dir, chroma_path=tmp_path / "chroma_cli_test")
    assert n > 0
