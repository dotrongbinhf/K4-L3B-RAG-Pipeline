"""Task 8 — Upload legal PDFs to PageIndex and retrieve cited pages."""

import hashlib
import json
import os
import re
import ssl
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent.parent
LEGAL_DIR = PROJECT_DIR / "data" / "landing" / "legal"
CACHE_PATH = PROJECT_DIR / "pageindex_doc_ids.json"
API_BASE = "https://api.pageindex.ai"
load_dotenv(PROJECT_DIR / ".env")


def _api_key() -> str:
    return os.getenv("PAGEINDEX_API_KEY", "").strip()


def _request(method: str, path: str, *, payload: dict | None = None,
             body: bytes | None = None, content_type: str = "application/json") -> dict:
    headers = {"api_key": _api_key()}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    if body is not None:
        headers["Content-Type"] = content_type
    request = Request(API_BASE + path, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ssl.SSLError, json.JSONDecodeError) as error:
        raise RuntimeError(f"PageIndex request failed: {error}") from error
    if not isinstance(result, dict):
        raise RuntimeError("Unexpected PageIndex response")
    return result


def _read_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("PageIndex cache must be a JSON object")
    return data


def upload_documents() -> None:
    """Upload local legal PDFs and cache their document IDs."""
    if not _api_key():
        raise RuntimeError("PAGEINDEX_API_KEY is not configured")
    pdfs = sorted(LEGAL_DIR.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No PDFs found in {LEGAL_DIR}")

    cache = _read_cache()
    for path in pdfs:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        current = cache.get(path.name)
        if isinstance(current, dict) and current.get("sha256") == digest and current.get("doc_id"):
            print(f"Already indexed: {path.name}")
            continue
        result = None
        for attempt in range(3):
            boundary = "----PageIndex" + uuid.uuid4().hex
            prefix = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
                "Content-Type: application/pdf\r\n\r\n"
            ).encode()
            body = prefix + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
            try:
                result = _request("POST", "/doc/", body=body,
                                  content_type=f"multipart/form-data; boundary={boundary}")
                break
            except (RuntimeError, ssl.SSLError) as error:
                if attempt == 2:
                    raise
                # The server may have accepted the upload before TLS closed.
                # Check PageIndex by exact filename before sending the PDF again.
                try:
                    listing = _request("GET", "/docs?limit=100&offset=0")
                    existing = next((item for item in listing.get("documents", [])
                                     if isinstance(item, dict) and item.get("name") == path.name), None)
                    if existing and (existing.get("id") or existing.get("doc_id")):
                        result = {"doc_id": existing.get("id") or existing.get("doc_id")}
                        break
                except Exception:
                    pass
                time.sleep(2 ** attempt)
        if result is None:
            raise RuntimeError(f"PageIndex upload failed for {path.name}")
        doc_id = result.get("doc_id")
        if not isinstance(doc_id, str) or not doc_id:
            raise RuntimeError(f"PageIndex did not return doc_id for {path.name}")
        cache[path.name] = {"doc_id": doc_id, "sha256": digest}
        CACHE_PATH.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")
        print(f"Submitted to PageIndex: {path.name}")


def _cached_documents() -> dict[str, str]:
    documents = {}
    for filename, entry in _read_cache().items():
        doc_id = entry if isinstance(entry, str) else entry.get("doc_id") if isinstance(entry, dict) else None
        if isinstance(doc_id, str) and doc_id:
            documents[filename] = doc_id
    return documents


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """Return PageIndex cited PDF pages in the shared SearchResult format."""
    if not isinstance(query, str) or not query.strip() or top_k <= 0:
        return []
    if not _api_key():
        return []
    documents = _cached_documents()
    if not documents:
        return []
    response = _request("POST", "/chat/completions", payload={
        "doc_id": list(documents.values()),
        "messages": [{"role": "user", "content": query.strip()}],
        "stream": False,
        "enable_citations": True,
    })
    answer = ""
    choices = response.get("choices", [])
    if choices and isinstance(choices[0], dict):
        answer = str(choices[0].get("message", {}).get("content") or "")
    citations = response.get("citations", [])
    citations = citations if isinstance(citations, list) else []
    citations += [
        {"document": match.group(1), "page": int(match.group(2))}
        for match in re.finditer(r"<doc=([^;>]+);page=(\d+)(?:;block=[^>]+)?", answer)
    ]
    by_id = {doc_id: filename for filename, doc_id in documents.items()}
    by_name = {Path(filename).name: (filename, doc_id) for filename, doc_id in documents.items()}
    pages: dict[str, dict[int, str]] = {}
    results = []
    seen = set()
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        ref = citation.get("doc_id") or citation.get("document_id") or citation.get("document") or citation.get("doc") or citation.get("file")
        filename = by_id.get(str(ref))
        if filename is None:
            match = by_name.get(Path(str(ref)).name)
            if match:
                filename = match[0]
        if filename is None:
            continue
        doc_id = documents[filename]
        try:
            page = int(citation.get("page") or citation.get("page_index") or citation.get("page_number"))
        except (TypeError, ValueError):
            continue
        key = (doc_id, page)
        if page < 1 or key in seen:
            continue
        seen.add(key)
        content = str(citation.get("text") or citation.get("snippet") or citation.get("content") or "").strip()
        if not content:
            if doc_id not in pages:
                raw = _request("GET", f"/doc/{quote(doc_id, safe='')}/?type=ocr&format=page")
                pages[doc_id] = {
                    int(item.get("page_index") or item.get("page")): str(item.get("markdown") or item.get("text") or "").strip()
                    for item in raw.get("result", [])
                    if isinstance(item, dict) and str(item.get("page_index") or item.get("page") or "").isdigit()
                }
            content = pages[doc_id].get(page, "")
        if not content:
            continue
        results.append({
            "id": f"pageindex::{doc_id}::page-{page}",
            "content": content,
            "score": 1.0 / (len(results) + 1),
            "metadata": {"source": Path(filename).name, "title": Path(filename).stem,
                         "doc_type": "legal", "url": None, "chunk_index": page - 1},
            "retrieval_method": "pageindex",
        })
        if len(results) >= top_k:
            break
    return results


if __name__ == "__main__":
    upload_documents()
