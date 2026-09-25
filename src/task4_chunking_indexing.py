"""
Task 4 — Chunking, embedding và indexing.

Hướng dẫn:
    1. Đọc toàn bộ Markdown trong data/standardized/.
    2. Chia văn bản bằng strategy đã chọn.
    3. Embed chunks bằng một provider duy nhất.
    4. Upsert vào ChromaDB với cosine distance.

Mỗi document/chunk phải theo docs/MODULE_CONTRACTS.md. ID cần ổn định để
chạy lại pipeline không tạo dữ liệu trùng. Task 5 phải dùng chung embed_texts().
"""
import os
import re
from pathlib import Path

from dotenv import load_dotenv

from .contracts import validate_document


load_dotenv()

STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
CHUNKING_METHOD = "recursive"
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024
COLLECTION_NAME = "rag_documents"

_MODEL = None


def _metadata_from_markdown(content: str, path: Path, doc_type: str) -> dict:
    title_match = re.search(r"^#\s+(.+)$", content, flags=re.MULTILINE)
    source_match = re.search(r"^\*\*Source:\*\*\s*(\S+)\s*$", content, flags=re.MULTILINE)
    return {
        "source": path.name,
        "title": title_match.group(1).strip() if title_match else path.stem,
        "doc_type": doc_type,
        "url": source_match.group(1) if source_match else None,
    }


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed text with the configured provider and one shared model contract."""
    if not texts:
        return []
    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("texts must contain non-empty strings")

    provider = os.getenv("EMBEDDING_PROVIDER", "sentence_transformers").lower()
    model_name = os.getenv("EMBEDDING_MODEL", EMBEDDING_MODEL)
    if provider == "sentence_transformers":
        global _MODEL
        if _MODEL is None:
            from sentence_transformers import SentenceTransformer

            _MODEL = SentenceTransformer(model_name)
        vectors = _MODEL.encode(texts, normalize_embeddings=True)
        return [list(map(float, vector)) for vector in vectors]
    if provider == "openai":
        from openai import OpenAI

        response = OpenAI().embeddings.create(model=model_name, input=texts)
        return [list(map(float, item.embedding)) for item in response.data]
    if provider == "gemini":
        from google import genai

        response = genai.Client().models.embed_content(model=model_name, contents=texts)
        return [list(map(float, item.values)) for item in response.embeddings]
    raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {provider}")


def get_collection():
    """Open the persistent Chroma collection configured for cosine distance."""
    import chromadb

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def load_documents() -> list[dict]:
    """Load non-empty Markdown files into contract-compliant Documents."""
    if not STANDARDIZED_DIR.is_dir():
        return []

    documents: list[dict] = []
    for path in sorted(STANDARDIZED_DIR.rglob("*.md")):
        if path.name.startswith("."):
            continue
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            continue
        relative = path.relative_to(STANDARDIZED_DIR)
        doc_type = "legal" if relative.parts[0] == "legal" else "news"
        document = {
            "id": relative.as_posix(),
            "content": content,
            "metadata": _metadata_from_markdown(content, path, doc_type),
        }
        validate_document(document)
        documents.append(document)
    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """Split Documents recursively while retaining stable identity and metadata."""
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        split_text = splitter.split_text
    except ImportError:
        def split_text(text: str) -> list[str]:
            step = max(1, CHUNK_SIZE - CHUNK_OVERLAP)
            return [text[start : start + CHUNK_SIZE] for start in range(0, len(text), step)]

    chunks: list[dict] = []
    for document in documents:
        validate_document(document)
        pieces = split_text(document["content"])
        for index, text in enumerate(pieces):
            content = text.strip()
            if not content:
                continue
            chunk = {
                "id": f"{document['id']}::chunk-{index}",
                "content": content,
                "metadata": {**document["metadata"], "chunk_index": index},
            }
            validate_document(chunk, require_chunk=True)
            chunks.append(chunk)
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Attach an embedding to every contract-compliant chunk."""
    if not chunks:
        return []
    for chunk in chunks:
        validate_document(chunk, require_chunk=True)
    vectors = embed_texts([chunk["content"] for chunk in chunks])
    if len(vectors) != len(chunks):
        raise RuntimeError("embedding provider returned an unexpected vector count")
    return [{**chunk, "embedding": vector} for chunk, vector in zip(chunks, vectors)]


def index_to_vectorstore(chunks: list[dict]) -> None:
    """Upsert chunks into Chroma so repeated runs do not duplicate IDs."""
    if not chunks:
        return
    collection = get_collection()
    collection.upsert(
        ids=[chunk["id"] for chunk in chunks],
        documents=[chunk["content"] for chunk in chunks],
        embeddings=[chunk["embedding"] for chunk in chunks],
        metadatas=[chunk["metadata"] for chunk in chunks],
    )


def run_pipeline() -> None:
    documents = load_documents()
    chunks = chunk_documents(documents)
    index_to_vectorstore(embed_chunks(chunks))
    print(f"Indexed {len(chunks)} chunks from {len(documents)} documents")


if __name__ == "__main__":
    run_pipeline()
