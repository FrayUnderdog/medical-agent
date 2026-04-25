from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


_DOCS_DIR = Path(__file__).resolve().parent / "docs" / "medical_knowledge"
_CHROMA_DIR = Path(__file__).resolve().parent / "chroma_db"


@dataclass(frozen=True)
class RagResult:
    retrieved_context: str
    sources: list[str]
    top_k: int
    retrieval_provider: str
    recall_top_k: int = 0
    rerank_top_n: int = 0
    reranker_provider: str | None = None
    reranker_used: bool = False
    retrieval_error: str | None = None


def _load_markdown_docs() -> list[tuple[str, str]]:
    docs: list[tuple[str, str]] = []
    if not _DOCS_DIR.exists():
        return docs
    for p in sorted(_DOCS_DIR.glob("*.md")):
        docs.append((p.name, p.read_text(encoding="utf-8")))
    return docs


def _keyword_retrieve(query: str, *, top_k: int, retrieval_error: str | None = None) -> RagResult:
    q = query.lower()
    # In fallback mode, keep responses tight and avoid unrelated docs.
    effective_k = min(top_k, 2)

    # Exact filename match ranking for known symptom docs.
    symptom_files: dict[str, str] = {
        "fever": "fever.md",
        "cough": "cough.md",
        "chest pain": "chest_pain.md",
        "headache": "headache.md",
        "shortness of breath": "shortness_of_breath.md",
    }

    mentioned: list[str] = []
    for phrase in symptom_files.keys():
        if phrase in q:
            mentioned.append(phrase)

    raw = _load_markdown_docs()
    if not raw:
        return RagResult(
            retrieved_context="",
            sources=[],
            top_k=effective_k,
            retrieval_provider="keyword_fallback",
            recall_top_k=0,
            rerank_top_n=0,
            reranker_provider=None,
            reranker_used=False,
            retrieval_error=retrieval_error,
        )

    # If the query mentions exactly one known symptom phrase, only retrieve from that doc.
    if len(mentioned) == 1:
        target = symptom_files[mentioned[0]]
        for source, text in raw:
            if source == target:
                return RagResult(
                    retrieved_context=text.strip()[:1200],
                    sources=[source],
                    top_k=1,
                    retrieval_provider="keyword_fallback",
                    recall_top_k=0,
                    rerank_top_n=0,
                    reranker_provider=None,
                    reranker_used=False,
                    retrieval_error=retrieval_error,
                )

    terms = [t for t in q.replace("_", " ").split() if len(t) > 2]

    scored: list[tuple[int, str, str]] = []
    for source, text in raw:
        lower = text.lower()
        score = sum(lower.count(t) for t in terms) if terms else 0
        # Prefer exact symptom filename match when present.
        base = source.removesuffix(".md").replace("_", " ")
        if base in q:
            score += 10
        scored.append((score, source, text))

    scored.sort(key=lambda x: x[0], reverse=True)
    picked = [x for x in scored if x[0] > 0][:effective_k]

    chunks: list[str] = []
    sources: list[str] = []
    for _, source, text in picked:
        sources.append(source)
        # Keep this simple: return the first ~1200 chars for context.
        chunks.append(text.strip()[:1200])

    return RagResult(
        retrieved_context="\n\n---\n\n".join(chunks).strip(),
        sources=sources,
        top_k=effective_k,
        retrieval_provider="keyword_fallback",
        recall_top_k=0,
        rerank_top_n=0,
        reranker_provider=None,
        reranker_used=False,
        retrieval_error=retrieval_error,
    )


def retrieve_medical_context(query: str, *, top_k: int = 4) -> RagResult:
    """
    Minimal RAG:
    - loads markdown docs from docs/medical_knowledge/
    - splits into chunks
    - embeds with OpenAIEmbeddings (text-embedding-3-small)
    - stores vectors in chroma_db/
    - retrieves top_k chunks for a query

    Fallback:
    - if OPENAI_API_KEY missing or embedding/vectorstore fails, use keyword retrieval.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return _keyword_retrieve(query, top_k=top_k, retrieval_error="Missing OPENAI_API_KEY")

    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from langchain_core.documents import Document
        from langchain_openai import OpenAIEmbeddings
        from langchain_chroma import Chroma

        raw_docs = _load_markdown_docs()
        if not raw_docs:
            return RagResult(
                retrieved_context="",
                sources=[],
                top_k=top_k,
                retrieval_provider="chroma_openai_embeddings",
                recall_top_k=0,
                rerank_top_n=0,
                reranker_provider=None,
                reranker_used=False,
            )

        splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=120)
        docs: list[Document] = []
        for source, text in raw_docs:
            docs.append(Document(page_content=text, metadata={"source": source}))

        chunks = splitter.split_documents(docs)

        embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=api_key)
        _CHROMA_DIR.mkdir(parents=True, exist_ok=True)

        vs = Chroma(
            collection_name="medical_knowledge",
            embedding_function=embeddings,
            persist_directory=str(_CHROMA_DIR),
        )

        # Add documents if the store is empty (or new on disk).
        try:
            existing = vs._collection.count()  # type: ignore[attr-defined]
        except Exception:
            existing = 0
        if existing == 0:
            vs.add_documents(chunks)

        recall_top_k = 6
        rerank_top_n = 3
        results = vs.similarity_search(query, k=recall_top_k)

        retrieved_chunks: list[str] = []
        sources: list[str] = []
        for d in results:
            retrieved_chunks.append(d.page_content.strip())
            src = (d.metadata or {}).get("source")
            if src and src not in sources:
                sources.append(str(src))

        reranker_used = False
        reranker_provider: str | None = None
        provider = "chroma_openai_embeddings"

        # Optional second-stage reranking.
        try:
            from reranker import rerank

            rr = rerank(query, retrieved_chunks, top_n=rerank_top_n)
            reranker_used = True
            reranker_provider = rr.provider
            provider = "chroma_openai_embeddings_bge_rerank"

            idx = [i for i in rr.indices if 0 <= i < len(retrieved_chunks)]
            if idx:
                retrieved_chunks = [retrieved_chunks[i] for i in idx]
                # Recompute sources in the same order as reranked chunks when possible.
                # (We keep unique sources, ordered by appearance.)
                new_sources: list[str] = []
                for i in idx:
                    src = (results[i].metadata or {}).get("source")
                    if src and str(src) not in new_sources:
                        new_sources.append(str(src))
                if new_sources:
                    sources = new_sources
        except Exception:
            # Fall back to embedding-only order.
            reranker_used = False
            reranker_provider = None
            provider = "chroma_openai_embeddings"

        # Final chunks: keep top_n.
        retrieved_chunks = retrieved_chunks[:rerank_top_n]

        return RagResult(
            retrieved_context="\n\n---\n\n".join(retrieved_chunks).strip(),
            sources=sources,
            top_k=len(retrieved_chunks),
            retrieval_provider=provider,
            recall_top_k=recall_top_k,
            rerank_top_n=rerank_top_n,
            reranker_provider=reranker_provider,
            reranker_used=reranker_used,
        )
    except Exception as e:
        msg = (str(e) or "").strip().replace("\n", " ")
        short = msg[:180]
        err = f"{type(e).__name__}: {short}" if short else type(e).__name__
        return _keyword_retrieve(query, top_k=top_k, retrieval_error=err)

