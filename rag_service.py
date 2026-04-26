from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_DOCS_DIR = Path(__file__).resolve().parent / "docs" / "medical_knowledge"
_CHROMA_DIR = Path(__file__).resolve().parent / "chroma_db"

# Retrieval confidence gate (Chroma distance-based scores normalized higher=better).
MIN_LOCAL_DOCS = 20
MIN_TOP_SCORE = 0.45
MIN_AVG_TOP5_SCORE = 0.35
RECALL_TOP_K = 20
RERANK_TOP_N = 3


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
    retrieval_trace: dict[str, Any] = field(default_factory=dict)


def _doc_title(markdown: str) -> str:
    for line in markdown.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
    return ""


def _knowledge_source_for_path(rel: str) -> str:
    rel_norm = rel.replace("\\", "/")
    if rel_norm.startswith("nhs_seed/"):
        return "offline_seed"
    return "offline_root"


def _load_markdown_docs() -> list[tuple[str, str, str]]:
    """
    Load all **/*.md under docs/medical_knowledge recursively.

    Returns list of (relative_filepath, text, title).
    """
    docs: list[tuple[str, str, str]] = []
    if not _DOCS_DIR.exists():
        return docs
    for p in sorted(_DOCS_DIR.rglob("*.md")):
        try:
            rel = str(p.relative_to(_DOCS_DIR)).replace("\\", "/")
            text = p.read_text(encoding="utf-8")
            title = _doc_title(text) or rel
            docs.append((rel, text, title))
        except OSError:
            continue
    return docs


def normalize_score(raw: float) -> tuple[float, str]:
    """
    Map Chroma/LangChain distance-style scores to (0,1] with higher = more similar.

    Chroma returns non-negative distances (L2 or cosine distance depending on config).
    Conservative mapping: 1 / (1 + d). Raw value recorded separately in trace.
    """
    if raw != raw:  # NaN
        return 0.0, "nan"
    d = max(float(raw), 0.0)
    return 1.0 / (1.0 + d), "inv_one_plus_distance"


def _keyword_retrieve(
    query: str,
    *,
    top_k: int,
    retrieval_error: str | None = None,
    latency_ms: int = 0,
) -> RagResult:
    q = query.lower()
    effective_k = min(top_k, RERANK_TOP_N)

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
        trace = _build_retrieval_trace(
            offline_retrieved_count=0,
            offline_top_score=0.0,
            offline_avg_top5_score=0.0,
            raw_scores_snapshot=[],
            normalized_scores_snapshot=[],
            fallback_triggered=True,
            fallback_reason="no_offline_docs",
            fallback_skipped=None,
            nhs_enabled=False,
            nhs_query=query,
            nhs_results_count=0,
            selected_sources=[],
            latency_ms=latency_ms,
            score_note="keyword_fallback",
        )
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
            retrieval_trace=trace,
        )

    if len(mentioned) == 1:
        target = symptom_files[mentioned[0]]
        for rel_path, text, _title in raw:
            if rel_path.endswith(target):
                srcs = [rel_path]
                trace = _build_retrieval_trace(
                    offline_retrieved_count=1,
                    offline_top_score=0.9,
                    offline_avg_top5_score=0.9,
                    raw_scores_snapshot=[{"filepath": rel_path, "raw_score": 0.0, "normalized_score": 0.9}],
                    normalized_scores_snapshot=[0.9],
                    fallback_triggered=True,
                    fallback_reason="keyword_single_doc_below_min_local_docs",
                    fallback_skipped="missing_api_key",
                    nhs_enabled=False,
                    nhs_query=query,
                    nhs_results_count=0,
                    selected_sources=srcs,
                    latency_ms=latency_ms,
                    score_note="keyword_fallback_single_symptom",
                )
                return RagResult(
                    retrieved_context=text.strip()[:1200],
                    sources=srcs,
                    top_k=1,
                    retrieval_provider="keyword_fallback",
                    recall_top_k=1,
                    rerank_top_n=1,
                    reranker_provider=None,
                    reranker_used=False,
                    retrieval_error=retrieval_error,
                    retrieval_trace=trace,
                )

    terms = [t for t in q.replace("_", " ").split() if len(t) > 2]

    scored: list[tuple[int, float, str, str]] = []
    for rel_path, text, _title in raw:
        lower = text.lower()
        score = sum(lower.count(t) for t in terms) if terms else 0
        base = Path(rel_path).stem.replace("_", " ")
        if base in q or base.replace(" ", "_") in q.replace(" ", "_"):
            score += 10
        if rel_path.lower().replace("\\", "/") in q:
            score += 3
        norm = min(1.0, 0.15 + 0.12 * float(score))
        scored.append((score, norm, rel_path, text))

    scored.sort(key=lambda x: x[0], reverse=True)
    picked = [x for x in scored if x[0] > 0][: max(effective_k, 5)]

    offline_count = len(picked)
    norms = [x[1] for x in picked[:5]] or [0.0]
    top_n = max(norms) if norms else 0.0
    avg5 = sum(norms) / max(len(norms), 1)

    fallback_triggered = (
        offline_count < MIN_LOCAL_DOCS
        or top_n < MIN_TOP_SCORE
        or avg5 < MIN_AVG_TOP5_SCORE
    )
    from nhs_content_client import NHSContentClient

    nhs = NHSContentClient()
    nhs_enabled = nhs.is_enabled()
    nhs_results: list[dict[str, Any]] = []
    fallback_skipped: str | None = None
    fallback_reason = ""
    if fallback_triggered:
        if not nhs_enabled:
            fallback_skipped = "missing_api_key"
            fallback_reason = "gate_triggered_no_nhs_key"
        else:
            nhs_results = nhs.search(query, limit=5)
            fallback_skipped = None
            fallback_reason = "gate_triggered_nhs_called"

    nhs_blocks: list[str] = []
    nhs_sources: list[str] = []
    for item in nhs_results:
        title = str(item.get("title") or "")
        summary = str(item.get("summary") or "")
        url = str(item.get("url") or "")
        nhs_blocks.append(f"### NHS reference: {title}\n{summary}\nURL: {url}\n")
        nhs_sources.append(f"nhs_api:{title}" if title else "nhs_api")

    chunks: list[str] = []
    sources: list[str] = []
    for _s, _norm, rel_path, text in picked[:effective_k]:
        sources.append(rel_path)
        chunks.append(text.strip()[:1200])

    for b in nhs_blocks:
        chunks.append(b)

    snap = [{"filepath": x[2], "raw_score": float(x[0]), "normalized_score": float(x[1])} for x in picked[:20]]

    trace = _build_retrieval_trace(
        offline_retrieved_count=offline_count,
        offline_top_score=float(top_n),
        offline_avg_top5_score=float(avg5),
        raw_scores_snapshot=snap,
        normalized_scores_snapshot=[float(x[1]) for x in picked[:20]],
        fallback_triggered=fallback_triggered,
        fallback_reason=fallback_reason or ("none" if not fallback_triggered else "gate"),
        fallback_skipped=fallback_skipped,
        nhs_enabled=nhs_enabled,
        nhs_query=query,
        nhs_results_count=len(nhs_results),
        selected_sources=sources + nhs_sources,
        latency_ms=latency_ms,
        score_note="keyword_term_heuristic",
    )

    return RagResult(
        retrieved_context="\n\n---\n\n".join(chunks).strip(),
        sources=sources + nhs_sources,
        top_k=len(chunks),
        retrieval_provider="keyword_fallback",
        recall_top_k=offline_count,
        rerank_top_n=effective_k,
        reranker_provider=None,
        reranker_used=False,
        retrieval_error=retrieval_error,
        retrieval_trace=trace,
    )


def _build_retrieval_trace(
    *,
    offline_retrieved_count: int,
    offline_top_score: float,
    offline_avg_top5_score: float,
    raw_scores_snapshot: list[dict[str, Any]],
    normalized_scores_snapshot: list[float],
    fallback_triggered: bool,
    fallback_reason: str,
    fallback_skipped: str | None,
    nhs_enabled: bool,
    nhs_query: str,
    nhs_results_count: int,
    selected_sources: list[str],
    latency_ms: int,
    score_note: str,
) -> dict[str, Any]:
    return {
        "offline_retrieved_count": offline_retrieved_count,
        "offline_top_score": offline_top_score,
        "offline_avg_top5_score": offline_avg_top5_score,
        "raw_scores_snapshot": raw_scores_snapshot,
        "normalized_scores_top": normalized_scores_snapshot[:20],
        "fallback_triggered": fallback_triggered,
        "fallback_reason": fallback_reason,
        "fallback_skipped": fallback_skipped,
        "nhs_enabled": nhs_enabled,
        "nhs_query": nhs_query,
        "nhs_results_count": nhs_results_count,
        "selected_sources": selected_sources,
        "latency_ms": latency_ms,
        "score_normalization": score_note,
    }


def retrieve_medical_context(query: str, *, top_k: int = 4) -> RagResult:
    """
    Hybrid RAG:
    - Recursive markdown under docs/medical_knowledge/**/*.md
    - Chroma + OpenAI embeddings when OPENAI_API_KEY is set
    - Confidence gate; optional NHS API transient context (no Chroma write)
    - Keyword fallback if embeddings unavailable
    """
    t0 = time.monotonic()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        lat = int((time.monotonic() - t0) * 1000)
        return _keyword_retrieve(query, top_k=top_k, retrieval_error="Missing OPENAI_API_KEY", latency_ms=lat)

    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from langchain_core.documents import Document
        from langchain_openai import OpenAIEmbeddings
        from langchain_chroma import Chroma

        raw_docs = _load_markdown_docs()
        if not raw_docs:
            lat = int((time.monotonic() - t0) * 1000)
            trace = _build_retrieval_trace(
                offline_retrieved_count=0,
                offline_top_score=0.0,
                offline_avg_top5_score=0.0,
                raw_scores_snapshot=[],
                normalized_scores_snapshot=[],
                fallback_triggered=True,
                fallback_reason="no_offline_docs",
                fallback_skipped=None,
                nhs_enabled=False,
                nhs_query=query,
                nhs_results_count=0,
                selected_sources=[],
                latency_ms=lat,
                score_note="none",
            )
            return RagResult(
                retrieved_context="",
                sources=[],
                top_k=top_k,
                retrieval_provider="chroma_openai_embeddings",
                recall_top_k=0,
                rerank_top_n=0,
                reranker_provider=None,
                reranker_used=False,
                retrieval_trace=trace,
            )

        splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=120)
        docs: list[Document] = []
        for rel_path, text, title in raw_docs:
            docs.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": rel_path,
                        "filepath": rel_path,
                        "title": title,
                        "knowledge_source": _knowledge_source_for_path(rel_path),
                    },
                )
            )

        chunks = splitter.split_documents(docs)

        embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=api_key)
        _CHROMA_DIR.mkdir(parents=True, exist_ok=True)

        vs = Chroma(
            collection_name="medical_knowledge",
            embedding_function=embeddings,
            persist_directory=str(_CHROMA_DIR),
        )

        try:
            existing = vs._collection.count()  # type: ignore[attr-defined]
        except Exception:
            existing = 0
        if existing == 0:
            vs.add_documents(chunks)

        results_with_scores = vs.similarity_search_with_score(query, k=RECALL_TOP_K)

        scored_rows: list[tuple[Document, float, float]] = []
        raw_snap: list[dict[str, Any]] = []
        norm_list: list[float] = []
        for doc, raw_score in results_with_scores:
            norm, note = normalize_score(float(raw_score))
            scored_rows.append((doc, float(raw_score), norm))
            meta = doc.metadata or {}
            raw_snap.append(
                {
                    "filepath": meta.get("filepath") or meta.get("source"),
                    "raw_score": float(raw_score),
                    "normalized_score": norm,
                    "normalization": note,
                }
            )
            norm_list.append(norm)

        offline_retrieved_count = len(scored_rows)
        offline_top_score = max(norm_list) if norm_list else 0.0
        top5 = norm_list[:5]
        offline_avg_top5_score = sum(top5) / max(len(top5), 1) if top5 else 0.0

        fallback_triggered = (
            offline_retrieved_count < MIN_LOCAL_DOCS
            or offline_top_score < MIN_TOP_SCORE
            or offline_avg_top5_score < MIN_AVG_TOP5_SCORE
        )

        from nhs_content_client import NHSContentClient

        nhs_client = NHSContentClient()
        nhs_enabled = nhs_client.is_enabled()
        nhs_results: list[dict[str, Any]] = []
        fallback_skipped: str | None = None
        fallback_reason = ""

        if fallback_triggered:
            if not nhs_enabled:
                fallback_skipped = "missing_api_key"
                fallback_reason = "confidence_gate_no_nhs_key"
            else:
                nhs_results = nhs_client.search(query, limit=5)
                fallback_reason = "confidence_gate_nhs_ok"
                if not nhs_results and nhs_client.last_error():
                    fallback_reason = f"confidence_gate_nhs_empty:{nhs_client.last_error()}"

        nhs_docs: list[Document] = []
        for item in nhs_results:
            title = str(item.get("title") or "NHS topic")
            summary = str(item.get("summary") or "")
            url = str(item.get("url") or "")
            page = f"### NHS reference: {title}\n{summary}\nURL: {url}\n"
            nhs_docs.append(
                Document(
                    page_content=page,
                    metadata={
                        "source": f"nhs_api:{title}",
                        "filepath": "",
                        "title": title,
                        "knowledge_source": "nhs_api_transient",
                    },
                )
            )

        combined_docs: list[Document] = [d for d, _r, _n in scored_rows] + nhs_docs
        retrieved_chunks = [d.page_content.strip() for d in combined_docs]

        reranker_used = False
        reranker_provider: str | None = None
        provider = "chroma_openai_embeddings"

        rerank_top_n = min(RERANK_TOP_N, top_k) if top_k else RERANK_TOP_N

        try:
            from reranker import rerank

            rr = rerank(query, retrieved_chunks, top_n=rerank_top_n)
            reranker_used = True
            reranker_provider = rr.provider
            provider = "chroma_openai_embeddings_bge_rerank"

            idx = [i for i in rr.indices if 0 <= i < len(combined_docs)]
            if idx:
                final_docs = [combined_docs[i] for i in idx]
            else:
                final_docs = combined_docs[:rerank_top_n]
        except Exception:
            reranker_used = False
            reranker_provider = None
            provider = "chroma_openai_embeddings"
            final_docs = combined_docs[:rerank_top_n]

        final_chunks = [d.page_content.strip() for d in final_docs]
        sources: list[str] = []
        for d in final_docs:
            src = (d.metadata or {}).get("source")
            if src and str(src) not in sources:
                sources.append(str(src))

        lat = int((time.monotonic() - t0) * 1000)
        trace = _build_retrieval_trace(
            offline_retrieved_count=offline_retrieved_count,
            offline_top_score=float(offline_top_score),
            offline_avg_top5_score=float(offline_avg_top5_score),
            raw_scores_snapshot=raw_snap,
            normalized_scores_snapshot=norm_list,
            fallback_triggered=fallback_triggered,
            fallback_reason=fallback_reason or ("none" if not fallback_triggered else "gate"),
            fallback_skipped=fallback_skipped,
            nhs_enabled=nhs_enabled,
            nhs_query=query,
            nhs_results_count=len(nhs_results),
            selected_sources=sources,
            latency_ms=lat,
            score_note="inv_one_plus_distance",
        )

        return RagResult(
            retrieved_context="\n\n---\n\n".join(final_chunks).strip(),
            sources=sources,
            top_k=len(final_chunks),
            retrieval_provider=provider,
            recall_top_k=RECALL_TOP_K,
            rerank_top_n=rerank_top_n,
            reranker_provider=reranker_provider,
            reranker_used=reranker_used,
            retrieval_trace=trace,
        )
    except Exception as e:
        msg = (str(e) or "").strip().replace("\n", " ")
        short = msg[:180]
        err = f"{type(e).__name__}: {short}" if short else type(e).__name__
        lat = int((time.monotonic() - t0) * 1000)
        return _keyword_retrieve(query, top_k=top_k, retrieval_error=err, latency_ms=lat)
