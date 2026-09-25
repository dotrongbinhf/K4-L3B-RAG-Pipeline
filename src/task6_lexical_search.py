"""Task 6: BM25 retrieval over the same chunks used by dense retrieval."""

import re

from .task4_chunking_indexing import chunk_documents, load_documents


CORPUS: list[dict] = []


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower(), flags=re.UNICODE)


def _get_corpus() -> list[dict]:
    return CORPUS if CORPUS else chunk_documents(load_documents())


def build_bm25_index(corpus: list[dict]):
    """Build a BM25 index from contract-compliant Task 4 chunks."""
    tokenized = [_tokenize(item["content"]) for item in corpus]
    try:
        from rank_bm25 import BM25Okapi

        return BM25Okapi(tokenized)
    except ImportError:
        class SimpleBM25:
            def __init__(self, documents: list[list[str]]) -> None:
                self.documents = documents

            def get_scores(self, query_tokens: list[str]) -> list[float]:
                return [
                    float(sum(document.count(token) for token in query_tokens))
                    for document in self.documents
                ]

        return SimpleBM25(tokenized)


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """Return unique BM25 SearchResults in descending BM25 score."""
    if not isinstance(query, str) or not query.strip() or top_k <= 0:
        return []
    corpus = _get_corpus()
    if not corpus:
        return []
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    bm25 = build_bm25_index(corpus)
    scores = bm25.get_scores(query_tokens)
    # In a very small corpus BM25's IDF can be zero (or negative) even for a
    # matching term.  Filter on token overlap rather than ``score > 0`` so a
    # relevant chunk is not discarded just because of that normalization.
    matching_indexes = [
        index
        for index, item in enumerate(corpus)
        if set(query_tokens).intersection(_tokenize(item["content"]))
    ]
    ranked = sorted(
        matching_indexes,
        key=lambda index: (-float(scores[index]), corpus[index]["id"]),
    )
    results: list[dict] = []
    seen: set[str] = set()
    for index in ranked:
        score = float(scores[index])
        item = corpus[index]
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        results.append(
            {
                "id": item["id"],
                "content": item["content"],
                "score": score,
                "metadata": item["metadata"],
                "retrieval_method": "bm25",
            }
        )
        if len(results) == top_k:
            break
    return results


if __name__ == "__main__":
    for result in lexical_search("Vietnam tourism food", top_k=3):
        print(result)
