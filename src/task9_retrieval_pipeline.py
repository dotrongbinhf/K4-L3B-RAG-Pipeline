"""
Task 9 — Retrieval pipeline hoàn chỉnh.

Luồng xử lý:
    1. Chạy semantic_search và lexical_search.
    2. Fuse hai danh sách bằng RRF đúng một lần.
    3. Lấy best cosine score gốc từ dense results.
    4. Nếu score dưới threshold, thử PageIndex fallback.
    5. Nếu fallback lỗi, trả hybrid results thay vì crash.

Không so sánh threshold với RRF score vì hai thang đo khác nhau.
"""
import math
import os

from dotenv import load_dotenv

from .task5_semantic_search import semantic_search
from .task6_lexical_search import lexical_search
from .task7_reranking import rerank_rrf
from .task8_pageindex_vectorless import pageindex_search


load_dotenv()
SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD", "0.3") or 0.3)
DEFAULT_TOP_K = 5


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    score_threshold: float = SCORE_THRESHOLD,
    use_reranking: bool = True,
) -> list[dict]:
    """Retrieve relevant chunks and use PageIndex when dense confidence is low.

    The confidence check always uses the best original dense cosine similarity.
    RRF is run at most once, and its score is never compared with the threshold.
    If PageIndex is unavailable or returns no results, the local result list is
    returned so a provider outage does not break the caller.
    """
    if not isinstance(query, str) or not query.strip():
        return []
    if not isinstance(top_k, int) or isinstance(top_k, bool):
        raise ValueError("top_k must be an integer")
    if top_k <= 0:
        return []
    if (
        not isinstance(score_threshold, (int, float))
        or isinstance(score_threshold, bool)
        or not math.isfinite(score_threshold)
    ):
        raise ValueError("score_threshold must be a finite number")
    if not isinstance(use_reranking, bool):
        raise ValueError("use_reranking must be a boolean")

    candidate_k = top_k * 2
    dense = semantic_search(query, top_k=candidate_k)
    sparse = lexical_search(query, top_k=candidate_k)
    if use_reranking:
        hybrid = rerank_rrf([dense, sparse], top_k=top_k)
    else:
        hybrid = dense[:top_k]

    best_dense_score = float(dense[0]["score"]) if dense else 0.0
    if best_dense_score < score_threshold:
        try:
            fallback = pageindex_search(query, top_k=top_k)
            if fallback:
                return fallback[:top_k]
        except Exception:
            pass
    return hybrid[:top_k]


if __name__ == "__main__":
    for result in retrieve("Vietnam tourism food", top_k=3):
        print(result)
