"""Task 8 — PageIndex fallback with a local vectorless backup.

PageIndex Cloud's document processing endpoint accepts PDFs. This task uploads
the group's source legal PDFs, caches document IDs, and requests cited pages for
queries. When the service, key, or citations are unavailable, a lightweight
local keyword retriever searches the standardized Markdown corpus instead.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


PROJECT_DIR = Path(__file__).resolve().parent.parent
STANDARDIZED_DIR = PROJECT_DIR / "data" / "standardized"
LEGAL_LANDING_DIR = PROJECT_DIR / "data" / "landing" / "legal"
CACHE_PATH = PROJECT_DIR / "pageindex_doc_ids.json"
API_BASE = "https://api.pageindex.ai"
UPLOAD_TIMEOUT_SECONDS = 120
CHAT_TIMEOUT_SECONDS = 90
OCR_TIMEOUT_SECONDS = 60
LOCAL_CHUNK_CHARS = 1600

logger = logging.getLogger(__name__)


def _load_environment() -> None:
    """Load .env when python-dotenv is installed, with a tiny stdlib fallback."""
    try:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_DIR / ".env")
        return
    except ImportError:
        pass

    env_path = PROJECT_DIR / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip("\"'")
        if name and value:
            os.environ.setdefault(name, value)


_load_environment()


def _api_key() -> str:
    """Read the key at call time so environment changes are picked up."""
    return os.getenv("PAGEINDEX_API_KEY", "").strip()


def _request_json(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = CHAT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    request_headers = {"api_key": _api_key(), **(headers or {})}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = Request(
        f"{API_BASE}{path}",
        data=body,
        headers=request_headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(
            f"PageIndex returned HTTP {error.code}: {detail}"
        ) from error
    except (URLError, TimeoutError) as error:
        raise RuntimeError(f"PageIndex request failed: {error}") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("PageIndex returned invalid JSON") from error
    if not isinstance(parsed, dict):
        raise RuntimeError("PageIndex response must be a JSON object")
    return parsed


def _multipart_upload(path: Path) -> dict[str, Any]:
    boundary = f"----ragpipeline{uuid.uuid4().hex}"
    prefix = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        "Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8")
    suffix = f"\r\n--{boundary}--\r\n".encode("ascii")
    data = prefix + path.read_bytes() + suffix
    request = Request(
        f"{API_BASE}/doc/",
        data=data,
        headers={
            "api_key": _api_key(),
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=UPLOAD_TIMEOUT_SECONDS) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(
            f"PageIndex upload failed with HTTP {error.code}: {detail}"
        ) from error
    except (URLError, TimeoutError) as error:
        raise RuntimeError(f"PageIndex upload failed: {error}") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("PageIndex upload returned invalid JSON") from error
    if not isinstance(parsed, dict):
        raise RuntimeError("PageIndex upload response must be a JSON object")
    return parsed


def _read_cache() -> dict[str, dict[str, str]]:
    if not CACHE_PATH.exists():
        return {}
    try:
        raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read PageIndex cache {CACHE_PATH}") from error
    if not isinstance(raw, dict):
        raise RuntimeError("PageIndex cache must contain a JSON object")

    # Migrate the previous simple {filename: doc_id} cache format in memory.
    normalized: dict[str, dict[str, str]] = {}
    for source, item in raw.items():
        if isinstance(item, str):
            normalized[source] = {"doc_id": item, "sha256": ""}
        elif (
            isinstance(item, dict)
            and isinstance(item.get("doc_id"), str)
            and isinstance(item.get("sha256", ""), str)
        ):
            normalized[source] = {
                "doc_id": item["doc_id"],
                "sha256": item.get("sha256", ""),
            }
    return normalized


def _write_cache(cache: dict[str, dict[str, str]]) -> None:
    temporary = CACHE_PATH.with_suffix(CACHE_PATH.suffix + ".tmp")
    temporary.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(CACHE_PATH)


def upload_documents() -> None:
    """Submit legal PDFs and persist their PageIndex IDs for later queries.

    The upload is idempotent for unchanged source files. If a PDF changes, a
    new PageIndex document is submitted and the cache points to the new ID.
    """
    api_key = _api_key()
    if not api_key:
        raise RuntimeError("PAGEINDEX_API_KEY is not configured in .env")

    pdfs = sorted(LEGAL_LANDING_DIR.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No source PDFs found in {LEGAL_LANDING_DIR}")

    cache = _read_cache()
    uploaded = 0
    for path in pdfs:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        current = cache.get(path.name)
        if current and current["sha256"] == digest and current["doc_id"]:
            print(f"Already indexed: {path.name}")
            continue

        response = _multipart_upload(path)
        doc_id = response.get("doc_id")
        if not isinstance(doc_id, str) or not doc_id.strip():
            raise RuntimeError(f"PageIndex did not return doc_id for {path.name}")
        cache[path.name] = {"doc_id": doc_id, "sha256": digest}
        _write_cache(cache)
        uploaded += 1
        print(f"Submitted to PageIndex: {path.name}")

    print(f"PageIndex upload complete: {uploaded} new PDF(s), {len(cache)} cached")


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[\w]+", text.casefold(), flags=re.UNICODE))


def _local_search(query: str, top_k: int) -> list[dict]:
    query_tokens = _tokens(query)
    if not query_tokens or not STANDARDIZED_DIR.is_dir():
        return []

    results: list[dict] = []
    for path in sorted(STANDARDIZED_DIR.rglob("*.md")):
        if not path.is_file() or path.name.startswith("."):
            continue
        try:
            document = path.read_text(encoding="utf-8")
        except OSError as error:
            logger.warning("Could not read local fallback source %s: %s", path, error)
            continue

        # Keep Markdown paragraphs together as small, readable evidence blocks.
        blocks = [block.strip() for block in re.split(r"\n\s*\n", document) if block.strip()]
        current: list[str] = []
        current_size = 0
        chunks: list[str] = []
        for block in blocks:
            if current and current_size + len(block) > LOCAL_CHUNK_CHARS:
                chunks.append("\n\n".join(current))
                current, current_size = [], 0
            current.append(block)
            current_size += len(block)
        if current:
            chunks.append("\n\n".join(current))

        relative = path.relative_to(STANDARDIZED_DIR)
        doc_type = "legal" if relative.parts and relative.parts[0] == "legal" else "news"
        for chunk_index, content in enumerate(chunks):
            overlap = len(query_tokens & _tokens(content))
            if overlap == 0:
                continue
            results.append(
                {
                    "id": f"pageindex::local::{relative.as_posix()}::{chunk_index}",
                    "content": content,
                    "score": overlap / len(query_tokens),
                    "metadata": {
                        "source": path.name,
                        "title": path.stem,
                        "doc_type": doc_type,
                        "url": None,
                        "chunk_index": chunk_index,
                    },
                    "retrieval_method": "pageindex",
                }
            )

    # Stable source/index tie-break keeps repeated queries deterministic.
    results.sort(
        key=lambda item: (
            -item["score"],
            item["metadata"]["source"],
            item["metadata"]["chunk_index"],
        )
    )
    return results[:top_k]


def _cached_documents() -> dict[str, str]:
    return {
        source: entry["doc_id"]
        for source, entry in _read_cache().items()
        if entry.get("doc_id")
    }


def _citation_page(citation: dict[str, Any]) -> int | None:
    page = citation.get("page") or citation.get("page_index") or citation.get("page_number")
    try:
        parsed = int(page)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _provider_search(query: str, top_k: int) -> list[dict]:
    documents = _cached_documents()
    if not documents:
        return []

    response = _request_json(
        "POST",
        "/chat/completions",
        payload={
            "doc_id": list(documents.values()),
            "messages": [{"role": "user", "content": query}],
            "stream": False,
            "enable_citations": True,
        },
        timeout=CHAT_TIMEOUT_SECONDS,
    )
    choices = response.get("choices", [])
    answer = ""
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message", {})
        if isinstance(message, dict):
            answer = str(message.get("content") or "")

    citations = response.get("citations", [])
    if not isinstance(citations, list):
        citations = []

    # Parse citation tags too; some API responses expose the tags in answer
    # text even when the structured citations array is absent.
    by_name = {Path(source).name: (source, doc_id) for source, doc_id in documents.items()}
    by_id = {doc_id: (source, doc_id) for source, doc_id in documents.items()}
    for match in re.finditer(
        r"<doc=(?P<doc>[^;>]+);page=(?P<page>\d+)(?:;block=[^>]+)?>", answer
    ):
        citations.append({"document": match.group("doc"), "page": match.group("page")})

    output: list[dict] = []
    seen: set[tuple[str, int]] = set()
    page_cache: dict[str, dict[int, str]] = {}
    for citation_rank, citation in enumerate(citations, start=1):
        if not isinstance(citation, dict):
            continue
        doc_ref = (
            citation.get("doc_id")
            or citation.get("document_id")
            or citation.get("document")
            or citation.get("doc")
            or citation.get("file")
        )
        reference = by_id.get(str(doc_ref)) or by_name.get(Path(str(doc_ref)).name)
        page_number = _citation_page(citation)
        if reference is None or page_number is None:
            continue
        source, doc_id = reference
        key = (doc_id, page_number)
        if key in seen:
            continue
        seen.add(key)

        content = str(
            citation.get("text")
            or citation.get("snippet")
            or citation.get("content")
            or ""
        ).strip()
        if not content:
            if doc_id not in page_cache:
                try:
                    raw = _request_json(
                        "GET",
                        f"/doc/{quote(doc_id, safe='')}/?type=ocr&format=page",
                        timeout=OCR_TIMEOUT_SECONDS,
                    )
                    page_cache[doc_id] = {}
                    pages = raw.get("result", [])
                    if isinstance(pages, list):
                        for page in pages:
                            if isinstance(page, dict):
                                number = page.get("page_index") or page.get("page")
                                try:
                                    page_cache[doc_id][int(number)] = str(
                                        page.get("markdown") or page.get("text") or ""
                                    ).strip()
                                except (TypeError, ValueError):
                                    continue
                except Exception as error:
                    logger.warning("Could not fetch cited OCR page: %s", error)
                    page_cache[doc_id] = {}
            content = page_cache.get(doc_id, {}).get(page_number, "")

        if not content:
            continue
        output.append(
            {
                "id": f"pageindex::{doc_id}::page-{page_number}",
                "content": content,
                "score": 1.0 / citation_rank,
                "metadata": {
                    "source": Path(source).name,
                    "title": Path(source).stem,
                    "doc_type": "legal",
                    "url": None,
                    "chunk_index": page_number - 1,
                },
                "retrieval_method": "pageindex",
            }
        )
        if len(output) >= top_k:
            break
    return output


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """Search PageIndex; return cited pages or local keyword evidence.

    Provider/API errors are logged and fall through to local Markdown search,
    so Task 9 and the Streamlit UI continue to work during an outage.
    """
    if not isinstance(query, str) or not query.strip():
        return []
    if not isinstance(top_k, int) or isinstance(top_k, bool):
        raise ValueError("top_k must be an integer")
    if top_k <= 0:
        return []

    if _api_key():
        try:
            results = _provider_search(query.strip(), top_k)
            if results:
                return results[:top_k]
        except Exception as error:
            logger.warning("PageIndex provider unavailable; using local fallback: %s", error)
    return _local_search(query.strip(), top_k)


if __name__ == "__main__":
    upload_documents()
