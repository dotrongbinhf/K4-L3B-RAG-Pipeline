"""
Hướng dẫn:
    1. Đọc PAGEINDEX_API_KEY từ .env.
    2. Upload tài liệu ở định dạng PageIndex hỗ trợ.
    3. Cache document IDs để không upload lại.
    4. Parse kết quả thành SearchResult có method pageindex.

PageIndex là dịch vụ ngoài: cần timeout và xử lý lỗi để pipeline không crash.
"""
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()
PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
LEGAL_LANDING_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"
_CACHE_PATH = Path(__file__).parent.parent / ".pageindex_documents.json"


def upload_documents() -> None:
    """Upload legal PDFs once and cache their PageIndex document IDs locally."""
    cache = json.loads(_CACHE_PATH.read_text(encoding="utf-8")) if _CACHE_PATH.exists() else {}
    if not PAGEINDEX_API_KEY:
        _CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")
        print("No PageIndex API key configured; skipped provider upload.")
        return

    import requests

    for path in sorted(LEGAL_LANDING_DIR.glob("*.pdf")):
        if path.name in cache:
            continue
        with path.open("rb") as file:
            response = requests.post(
                "https://api.pageindex.ai/doc/",
                headers={"api_key": PAGEINDEX_API_KEY},
                files={"file": (path.name, file, "application/pdf")},
                timeout=120,
            )
        response.raise_for_status()
        doc_id = response.json().get("doc_id")
        if not doc_id:
            raise RuntimeError(f"PageIndex did not return doc_id for {path.name}")
        cache[path.name] = doc_id
        _CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")
        print(f"Uploaded: {path.name}")


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower(), flags=re.UNICODE))


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """Return vectorless SearchResults without allowing provider failure to crash callers."""
    if not isinstance(query, str) or not query.strip() or top_k <= 0:
        return []
    if PAGEINDEX_API_KEY and _CACHE_PATH.exists():
        try:
            import requests

            cache = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
            response = requests.post(
                "https://api.pageindex.ai/chat/completions",
                headers={"api_key": PAGEINDEX_API_KEY},
                json={
                    "messages": [{"role": "user", "content": query}],
                    "doc_id": list(cache.values()),
                    "enable_citations": True,
                },
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
            answer = payload.get("answer") or payload.get("content") or ""
            citations = payload.get("citations", [])
            source_by_doc_id = {doc_id: source for source, doc_id in cache.items()}
            provider_results = []
            for rank, citation in enumerate(citations[:top_k], start=1):
                doc_id = citation.get("doc_id") or citation.get("document_id")
                source = source_by_doc_id.get(doc_id, "pageindex.pdf")
                provider_results.append(
                    {
                        "id": f"pageindex::{doc_id or rank}::{rank}",
                        "content": citation.get("text") or answer,
                        "score": 1.0 / rank,
                        "metadata": {
                            "source": source,
                            "title": Path(source).stem,
                            "doc_type": "legal",
                            "url": None,
                            "chunk_index": rank - 1,
                        },
                        "retrieval_method": "pageindex",
                    }
                )
            if provider_results:
                return provider_results
        except Exception:
            pass
    query_tokens = _tokens(query)
    candidates: list[dict] = []
    if not STANDARDIZED_DIR.is_dir():
        return []
    for path in sorted(STANDARDIZED_DIR.rglob("*.md")):
        if not path.is_file() or path.name.startswith("."):
            continue
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            continue
        score = float(len(query_tokens & _tokens(content)))
        if score <= 0:
            continue
        relative = path.relative_to(STANDARDIZED_DIR)
        candidates.append(
            {
                "id": f"pageindex::{relative.as_posix()}",
                "content": content,
                "score": score,
                "metadata": {
                    "source": path.name,
                    "title": path.stem,
                    "doc_type": "legal" if relative.parts[0] == "legal" else "news",
                    "url": None,
                    "chunk_index": 0,
                },
                "retrieval_method": "pageindex",
            }
        )
    return sorted(candidates, key=lambda item: item["score"], reverse=True)[:top_k]


if __name__ == "__main__":
    upload_documents()
