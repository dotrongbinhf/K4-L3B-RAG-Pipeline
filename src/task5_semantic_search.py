"""
Task 5 — Semantic search.

Embed query bằng chính hàm của Task 4, query ChromaDB và đổi cosine distance
thành similarity. Output phải theo SearchResult, sort giảm dần và không quá top_k.
"""
from .task4_chunking_indexing import embed_texts, get_collection


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """Return unique dense SearchResults in descending cosine similarity."""
    if not isinstance(query, str) or not query.strip() or top_k <= 0:
        return []
    collection = get_collection()
    if hasattr(collection, "count") and collection.count() == 0:
        return []
    query_vector = embed_texts([query])[0]
    collection_size = collection.count() if hasattr(collection, "count") else top_k
    response = collection.query(
        query_embeddings=[query_vector],
        n_results=min(top_k, collection_size),
        include=["documents", "metadatas", "distances"],
    )
    results: list[dict] = []
    seen: set[str] = set()
    for item_id, content, metadata, distance in zip(
        response.get("ids", [[]])[0],
        response.get("documents", [[]])[0],
        response.get("metadatas", [[]])[0],
        response.get("distances", [[]])[0],
    ):
        if item_id in seen:
            continue
        seen.add(item_id)
        # Chroma omits metadata fields whose stored value is ``None``. Restore
        # the optional URL key so downstream SearchResults keep the contract.
        normalized_metadata = {**(metadata or {}), "url": (metadata or {}).get("url")}
        results.append(
            {
                "id": item_id,
                "content": content,
                "score": max(0.0, 1.0 - float(distance)),
                "metadata": normalized_metadata,
                "retrieval_method": "dense",
            }
        )
    return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]


if __name__ == "__main__":
    for result in semantic_search("Vietnam tourism food", top_k=3):
        print(result)
