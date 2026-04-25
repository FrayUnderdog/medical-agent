from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RerankResult:
    indices: list[int]
    provider: str


_MODEL_ID = "BAAI/bge-reranker-base"
_tokenizer = None
_model = None


def _lazy_load():
    global _tokenizer, _model
    if _tokenizer is not None and _model is not None:
        return _tokenizer, _model

    # Optional dependency: if transformers/torch aren't installed, callers should fall back.
    from transformers import AutoModelForSequenceClassification, AutoTokenizer  # type: ignore

    tok = AutoTokenizer.from_pretrained(_MODEL_ID)
    mdl = AutoModelForSequenceClassification.from_pretrained(_MODEL_ID)
    mdl.eval()
    _tokenizer, _model = tok, mdl
    return tok, mdl


def rerank(query: str, passages: list[str], *, top_n: int) -> RerankResult:
    """
    Minimal local BGE reranker.

    - Returns indices of the best passages by relevance.
    - Raises if dependencies/model load/inference fails (caller should catch and fall back).
    """
    if not passages:
        return RerankResult(indices=[], provider="bge_reranker")

    tok, mdl = _lazy_load()

    # Score each (query, passage) pair. Keep it simple; no batching assumptions.
    import torch  # type: ignore

    scores: list[tuple[float, int]] = []
    for i, p in enumerate(passages):
        inputs = tok(query, p, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            out = mdl(**inputs)
            # Commonly a single logit for relevance.
            logit = out.logits.squeeze().float().item()
        scores.append((logit, i))

    scores.sort(key=lambda x: x[0], reverse=True)
    picked = [i for _, i in scores[: max(top_n, 0)]]
    return RerankResult(indices=picked, provider=_MODEL_ID)

