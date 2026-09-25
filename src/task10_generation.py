"""
Task 10 — Generation có citation.

Hướng dẫn:
    1. Retrieve top-k chunks.
    2. Reorder để giảm lost-in-the-middle.
    3. Format context kèm title và source.
    4. Gọi provider được chọn trong .env.
    5. Trả answer, sources và retrieval_source.

Nếu context không đủ hoặc provider lỗi, trả safe refusal; không bịa thông tin.
"""
import os

from dotenv import load_dotenv

from .task9_retrieval_pipeline import retrieve


load_dotenv()
TOP_K = 5
TOP_P = 0.9
TEMPERATURE = 0.3
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
LLM_MODEL = os.getenv("LLM_MODEL", "")
SAFE_REFUSAL = "Tôi không thể xác minh thông tin này từ nguồn hiện có."
SYSTEM_PROMPT = """Answer only with the supplied context. Cite supporting documents as
[Document N]. If the context does not support an answer, say that it cannot be verified."""


def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """Move alternating lower-ranked chunks to the end without mutating input."""
    if len(chunks) <= 2:
        return list(chunks)
    return list(chunks[::2]) + list(chunks[1::2])[::-1]


def format_context(chunks: list[dict]) -> str:
    """Format evidence with stable labels that the model can cite."""
    parts = []
    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk["metadata"]
        parts.append(
            f"[Document {index} | Title: {metadata['title']} | Source: {metadata['source']}]\n"
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
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
            temperature=TEMPERATURE,
            top_p=TOP_P,
        )
        return response.choices[0].message.content.strip()
    if provider == "gemini":
        from google import genai

        response = genai.Client().models.generate_content(
            model=model,
            contents=f"{system_prompt}\n\n{user_message}",
        )
        return response.text.strip()
    if provider == "anthropic":
        from anthropic import Anthropic

        response = Anthropic().messages.create(
            model=model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return "".join(block.text for block in response.content if block.type == "text").strip()
    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """Retrieve evidence and generate a grounded GenerationResult."""
    chunks = retrieve(query, top_k=top_k)
    if not chunks:
        return {"answer": SAFE_REFUSAL, "sources": [], "retrieval_source": "none"}
    context = format_context(reorder_for_llm(chunks))
    message = f"Context:\n{context}\n\nQuestion: {query}"
    try:
        answer = call_llm(SYSTEM_PROMPT, message)
    except Exception:
        answer = SAFE_REFUSAL
    if not answer:
        answer = SAFE_REFUSAL
    return {
        "answer": answer,
        "sources": chunks,
        "retrieval_source": chunks[0]["retrieval_method"],
    }


if __name__ == "__main__":
    print(generate_with_citation("Vietnam tourism food"))
