"""
Ingest knowledge_base/ markdown files into ChromaDB.

Usage:
    python -m app.rag.ingest

The embedding provider is selected via RAG_EMBEDDING_PROVIDER (.env):
    onnx   (default) — local, no API key required
    openai            — OpenAI text-embedding-3-small (requires OPENAI_API_KEY)
"""
from __future__ import annotations

import sys
from pathlib import Path

# Absolute project root — reliable regardless of CWD.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def chunk_text(text: str, max_chars: int = 500) -> list[str]:
    """Split on blank lines; further split paragraphs that exceed max_chars."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    for para in paragraphs:
        # Strip markdown headers — keep only body text in the chunk
        lines = [ln for ln in para.split("\n") if not ln.startswith("#")]
        para = " ".join(lines).strip()
        if not para:
            continue
        while len(para) > max_chars:
            split_at = para.rfind(". ", 0, max_chars)
            if split_at == -1:
                split_at = max_chars
            chunk = para[: split_at + 1].strip()
            if chunk:
                chunks.append(chunk)
            para = para[split_at + 1 :].strip()
        if para:
            chunks.append(para)
    return chunks


def load_documents(kb_dir: Path) -> list[dict]:
    """Load and chunk all .md files. Returns list of {id, source, content}."""
    docs: list[dict] = []
    for md_file in sorted(kb_dir.glob("*.md")):
        source = md_file.stem
        text = md_file.read_text(encoding="utf-8")
        for i, content in enumerate(chunk_text(text)):
            docs.append({"id": f"{source}_{i}", "source": source, "content": content})
    return docs


def ingest_into_collection(collection, kb_dir: Path) -> int:
    """Upsert documents into an existing ChromaDB collection. Returns chunk count."""
    docs = load_documents(kb_dir)
    if not docs:
        return 0
    collection.upsert(
        ids=[d["id"] for d in docs],
        documents=[d["content"] for d in docs],
        metadatas=[{"source": d["source"]} for d in docs],
    )
    return len(docs)


def ingest(kb_dir: Path | None = None, chroma_path: Path | None = None) -> int:
    """
    Standalone ingest — creates its own ChromaDB client and collection.

    If RAG_EMBEDDING_PROVIDER=openai and the OpenAI embedding call fails,
    automatically retries with ONNX embeddings and logs a warning.
    """
    import chromadb
    from app.config import settings
    from app.rag.embedding import make_embedding_function, onnx_embedding_function

    kb_dir = kb_dir or _PROJECT_ROOT / "knowledge_base"
    chroma_path = chroma_path or Path(settings.chroma_path)
    chroma_path.mkdir(parents=True, exist_ok=True)

    ef = make_embedding_function()
    client = chromadb.PersistentClient(path=str(chroma_path))
    collection = client.get_or_create_collection(
        name="knowledge_base",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    try:
        return ingest_into_collection(collection, kb_dir)
    except Exception as exc:
        if settings.rag_embedding_provider == "openai":
            print(
                f"WARNING: OpenAI embedding failed ({type(exc).__name__}: {exc})\n"
                "Falling back to ONNX embeddings..."
            )
            try:
                client.delete_collection("knowledge_base")
            except Exception:
                pass
            collection = client.get_or_create_collection(
                name="knowledge_base",
                embedding_function=onnx_embedding_function(),
                metadata={"hnsw:space": "cosine"},
            )
            return ingest_into_collection(collection, kb_dir)
        raise


if __name__ == "__main__":
    from app.config import settings as _settings

    _kb_dir = _PROJECT_ROOT / "knowledge_base"
    _chroma_path = Path(_settings.chroma_path)

    print(f"Knowledge base : {_kb_dir}")
    print(f"ChromaDB path  : {_chroma_path.resolve()}")
    print(f"Embedding      : {_settings.rag_embedding_provider}")

    if not _kb_dir.exists():
        print(f"ERROR: knowledge_base/ not found at {_kb_dir}")
        sys.exit(1)

    n = ingest(kb_dir=_kb_dir, chroma_path=_chroma_path)
    print(f"Ingested {n} chunks into ChromaDB.")
    sys.exit(0 if n > 0 else 1)
