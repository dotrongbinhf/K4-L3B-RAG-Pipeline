"""Task 10 — Generate grounded answers with verifiable citations."""

import os
import re
import time

from dotenv import load_dotenv

from .task8_pageindex_vectorless import pageindex_search
from .task9_retrieval_pipeline import SCORE_THRESHOLD, retrieve


load_dotenv()
TOP_K = 5
TOP_P = 0.9
TEMPERATURE = 0.3
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
LLM_MODEL = os.getenv("LLM_MODEL", "")
SAFE_REFUSAL = "Tôi không thể xác minh thông tin này từ nguồn hiện có."
SYSTEM_PROMPT = """Bạn là trợ lý hỏi đáp dựa trên tài liệu.
Chỉ trả lời bằng thông tin có trong context được cung cấp.
Mỗi khẳng định phải trích dẫn ít nhất một nhãn theo đúng dạng [Document N].
Không tự tạo URL, tên nguồn hay số hiệu văn bản.
Nếu context không đủ bằng chứng, hãy nói không thể xác minh thay vì suy đoán."""

_CITATION_PATTERN = re.compile(r"\[Document\s+(\d+)\]", flags=re.IGNORECASE)
_RETRIEVAL_STRATEGIES = {"auto", "hybrid", "pageindex"}


def _safe_result() -> dict:
    """Return the canonical result when no verifiable answer is available."""
    return {"answer": SAFE_REFUSAL, "sources": [], "retrieval_source": "none"}


def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """Reduce lost-in-the-middle risk without mutating chunks or their IDs."""
    if len(chunks) <= 2:
        return list(chunks)
    return list(chunks[::2]) + list(chunks[1::2])[::-1]


def format_context(chunks: list[dict]) -> str:
    """Format evidence with stable labels that map back to ``sources``."""
    parts: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk["metadata"]
        citation_index = chunk.get("_citation_index", index)
        parts.append(
            f"[Document {citation_index}]\n"
            f"Title: {metadata['title']}\n"
            f"Source: {metadata['source']}\n"
            f"Chunk ID: {chunk['id']}\n"
            f"{chunk['content']}"
        )
    return "\n\n---\n\n".join(parts)


def call_llm(system_prompt: str, user_message: str) -> str:
    """Call the configured provider and return plain response text."""
    provider = os.getenv("LLM_PROVIDER", LLM_PROVIDER).lower()
    model = os.getenv("LLM_MODEL", LLM_MODEL)
    if not model:
        raise RuntimeError("LLM_MODEL is not configured")

    if provider == "openai":
        from openai import OpenAI

        response = OpenAI().chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=TEMPERATURE,
            top_p=TOP_P,
        )
        return (response.choices[0].message.content or "").strip()

    if provider == "gemini":
        from google import genai

        response = genai.Client().models.generate_content(
            model=model,
            contents=f"{system_prompt}\n\n{user_message}",
        )
        return (response.text or "").strip()

    if provider == "anthropic":
        from anthropic import Anthropic

        response = Anthropic().messages.create(
            model=model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return "".join(
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        ).strip()

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


def _generate_from_chunks(query: str, chunks: list[dict]) -> dict:
    """Generate an answer from already-retrieved chunks."""
    if not chunks:
        return _safe_result()

    # Sources stay in descending retrieval-score order as required by the
    # contract. Context can be reordered because every block keeps the number
    # of its matching element in ``sources``.
    labeled_chunks = [
        {**chunk, "_citation_index": index}
        for index, chunk in enumerate(chunks, start=1)
    ]
    context = format_context(reorder_for_llm(labeled_chunks))
    user_message = f"Context:\n{context}\n\nQuestion: {query}"

    try:
        answer = call_llm(SYSTEM_PROMPT, user_message).strip()
    except Exception:
        return _safe_result()

    citation_indexes = [int(value) for value in _CITATION_PATTERN.findall(answer)]
    if (
        not answer
        or not citation_indexes
        or any(index < 1 or index > len(chunks) for index in citation_indexes)
    ):
        return _safe_result()

    retrieval_source = (
        "pageindex"
        if all(chunk.get("retrieval_method") == "pageindex" for chunk in chunks)
        else "hybrid"
    )
    return {
        "answer": answer,
        "sources": chunks,
        "retrieval_source": retrieval_source,
    }


def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """Retrieve evidence and generate a grounded GenerationResult."""
    if not isinstance(query, str) or not query.strip():
        return _safe_result()

    try:
        chunks = retrieve(query, top_k=top_k)
    except Exception:
        return _safe_result()
    return _generate_from_chunks(query, chunks)


def generate_with_options(
    query: str,
    top_k: int = TOP_K,
    strategy: str = "auto",
    score_threshold: float = SCORE_THRESHOLD,
) -> tuple[dict, dict]:
    """Generate an answer and return UI diagnostics without changing the contract.

    ``generate_with_citation`` remains the required public lab interface. This
    helper adds selectable retrieval routes and timing/score diagnostics for
    the Streamlit UI while keeping metrics outside ``GenerationResult``.
    """
    if strategy not in _RETRIEVAL_STRATEGIES:
        raise ValueError(f"Unsupported retrieval strategy: {strategy}")

    started_at = time.perf_counter()
    retrieval_started_at = time.perf_counter()
    retrieval_failed = False
    try:
        if strategy == "auto":
            chunks = retrieve(
                query,
                top_k=top_k,
                score_threshold=score_threshold,
            )
        elif strategy == "hybrid":
            # A threshold of -1 disables PageIndex fallback and retains Hybrid + RRF.
            chunks = retrieve(query, top_k=top_k, score_threshold=-1.0)
        else:
            chunks = pageindex_search(query, top_k=top_k)
    except Exception:
        chunks = []
        retrieval_failed = True
    retrieval_ms = (time.perf_counter() - retrieval_started_at) * 1000

    generation_started_at = time.perf_counter()
    result = (
        _generate_from_chunks(query, chunks)
        if isinstance(query, str) and query.strip()
        else _safe_result()
    )
    generation_ms = (time.perf_counter() - generation_started_at) * 1000

    scores = [float(chunk["score"]) for chunk in chunks]
    methods = sorted({chunk.get("retrieval_method", "unknown") for chunk in chunks})
    citation_count = len(set(_CITATION_PATTERN.findall(result["answer"])))
    metrics = {
        "strategy": strategy,
        "retrieval_ms": retrieval_ms,
        "generation_ms": generation_ms,
        "total_ms": (time.perf_counter() - started_at) * 1000,
        "retrieved_count": len(chunks),
        "source_count": len(result["sources"]),
        "citation_count": citation_count,
        "top_score": max(scores) if scores else None,
        "average_score": sum(scores) / len(scores) if scores else None,
        "score_type": "+".join(methods) if methods else "none",
        "fallback_used": strategy == "auto" and result["retrieval_source"] == "pageindex",
        "retrieval_failed": retrieval_failed,
        "score_threshold": score_threshold if strategy == "auto" else None,
    }
    return result, metrics


if __name__ == "__main__":
    print(generate_with_citation("Ẩm thực Việt Nam có những món ăn nào nổi bật?"))
