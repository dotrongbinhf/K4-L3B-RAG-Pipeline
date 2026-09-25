"""Task 7 — Reciprocal Rank Fusion (RRF).

RRF combines ranked result lists without mixing incompatible raw scores such
as cosine similarity and BM25. For a result ``d``, its fused score is
``sum(1 / (k + rank))`` across lists containing ``d``; ranks start at 1.

The output uses the shared SearchResult schema and marks every result as
``hybrid``. RRF scores represent rank agreement, not semantic similarity, so
they must not be used for the dense-score fallback threshold.
"""

import math


_VALID_METHODS = {"dense", "bm25", "hybrid", "pageindex"}


def _validate_result(item: object, list_index: int, rank: int) -> tuple[str, dict]:
    """Validate the fields RRF needs and the fields its output must preserve."""
    location = f"ranked_lists[{list_index}][{rank - 1}]"
    if not isinstance(item, dict):
        raise ValueError(f"{location} must be a SearchResult dict")

    item_id = item.get("id")
    if not isinstance(item_id, str) or not item_id.strip():
        raise ValueError(f"{location}.id must be a non-empty string")
    if not isinstance(item.get("content"), str) or not item["content"].strip():
        raise ValueError(f"{location}.content must be a non-empty string")

    metadata = item.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError(f"{location}.metadata must be a dict")
    for key in ("source", "title", "doc_type"):
        if not isinstance(metadata.get(key), str) or not metadata[key].strip():
            raise ValueError(f"{location}.metadata.{key} must be a non-empty string")
    if "url" not in metadata or not (
        metadata["url"] is None or isinstance(metadata["url"], str)
    ):
        raise ValueError(f"{location}.metadata.url must be a string or None")
    chunk_index = metadata.get("chunk_index")
    if (
        not isinstance(chunk_index, int)
        or isinstance(chunk_index, bool)
        or chunk_index < 0
    ):
        raise ValueError(
            f"{location}.metadata.chunk_index must be a non-negative integer"
        )

    raw_score = item.get("score")
    if (
        not isinstance(raw_score, (int, float))
        or isinstance(raw_score, bool)
        or not math.isfinite(raw_score)
    ):
        raise ValueError(f"{location}.score must be a finite number")
    if item.get("retrieval_method") not in _VALID_METHODS:
        raise ValueError(f"{location}.retrieval_method is invalid")

    return item_id, item


def rerank_rrf(
    ranked_lists: list[list[dict]],
    top_k: int = 5,
    k: int = 60,
) -> list[dict]:
    """Fuse ranked SearchResult lists and return at most ``top_k`` results.

    Duplicate IDs across retrievers receive evidence from each retriever, but
    each ID contributes at most once per input list. The first copy's content
    and metadata are preserved, and inputs are never mutated.
    """
    if not isinstance(ranked_lists, list):
        raise ValueError("ranked_lists must be a list of ranked lists")
    if not isinstance(top_k, int) or isinstance(top_k, bool):
        raise ValueError("top_k must be an integer")
    if not isinstance(k, int) or isinstance(k, bool):
        raise ValueError("k must be an integer")
    if top_k <= 0:
        return []
    if k < 0:
        raise ValueError("k must be non-negative")

    scores: dict[str, float] = {}
    items: dict[str, dict] = {}
    for list_index, ranked_list in enumerate(ranked_lists):
        if not isinstance(ranked_list, list):
            raise ValueError(f"ranked_lists[{list_index}] must be a list")

        seen_in_list: set[str] = set()
        for rank, item in enumerate(ranked_list, start=1):
            item_id, validated_item = _validate_result(item, list_index, rank)
            # A duplicate ID must not receive multiple votes from one retriever.
            if item_id in seen_in_list:
                continue
            seen_in_list.add(item_id)
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
            items.setdefault(item_id, validated_item)

    # ID is a deterministic tie-break when fused scores are equal.
    ordered_ids = sorted(scores, key=lambda item_id: (-scores[item_id], item_id))
    return [
        {
            **items[item_id],
            "score": scores[item_id],
            "retrieval_method": "hybrid",
        }
        for item_id in ordered_ids[:top_k]
    ]


if __name__ == "__main__":
    # A runnable mock example: no embeddings, vector DB, or API required.
    def mock_result(item_id: str, content: str, score: float, method: str) -> dict:
        return {
            "id": item_id,
            "content": content,
            "score": score,
            "metadata": {
                "source": f"{item_id}.md",
                "title": item_id.replace("-", " ").title(),
                "doc_type": "news",
                "url": None,
                "chunk_index": 0,
            },
            "retrieval_method": method,
        }

    dense = [
        mock_result("hoi-an", "Hoi An travel guide", 0.91, "dense"),
        mock_result("ha-long", "Ha Long Bay travel guide", 0.82, "dense"),
    ]
    bm25 = [
        mock_result("ha-long", "Ha Long Bay travel guide", 8.4, "bm25"),
        mock_result("hoi-an", "Hoi An travel guide", 5.2, "bm25"),
    ]

    print("Fused results (top_k=2):")
    for result in rerank_rrf([dense, bm25], top_k=2):
        print(
            f"{result['id']}: RRF={result['score']:.6f}, "
            f"method={result['retrieval_method']}"
        )
