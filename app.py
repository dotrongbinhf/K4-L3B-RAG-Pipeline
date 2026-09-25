"""Streamlit interface for the end-to-end RAG pipeline."""

import streamlit as st
from dotenv import load_dotenv

from src.task10_generation import SAFE_REFUSAL, generate_with_options
from src.task9_retrieval_pipeline import SCORE_THRESHOLD


load_dotenv()

st.set_page_config(
    page_title="Trợ lý Du lịch Việt Nam",
    page_icon="🧭",
    layout="wide",
)


STRATEGY_OPTIONS = {
    "Tự động: Hybrid + RRF → fallback": "auto",
    "Hybrid + RRF (không fallback)": "hybrid",
    "PageIndex trực tiếp": "pageindex",
}


def render_metrics(metrics: dict) -> None:
    """Show retrieval and generation diagnostics for one answer."""
    if not metrics:
        return

    timing_columns = st.columns(3)
    timing_columns[0].metric("Tổng thời gian", f"{metrics['total_ms'] / 1000:.2f}s")
    timing_columns[1].metric("Retrieval", f"{metrics['retrieval_ms'] / 1000:.2f}s")
    timing_columns[2].metric("Generation", f"{metrics['generation_ms'] / 1000:.2f}s")

    count_columns = st.columns(3)
    count_columns[0].metric("Chunks retrieve", metrics["retrieved_count"])
    count_columns[1].metric("Nguồn trả về", metrics["source_count"])
    count_columns[2].metric("Citation", metrics["citation_count"])

    top_score = metrics.get("top_score")
    average_score = metrics.get("average_score")
    score_summary = (
        f"Top score: {top_score:.4f} · Average score: {average_score:.4f}"
        if top_score is not None and average_score is not None
        else "Không có retrieval score."
    )
    threshold = metrics.get("score_threshold")
    threshold_text = f" · Dense fallback threshold: {threshold:.2f}" if threshold is not None else ""
    fallback_text = " · Đã dùng fallback" if metrics.get("fallback_used") else ""
    st.caption(
        f"Strategy: {metrics['strategy']} · Score type: {metrics['score_type']} · "
        f"{score_summary}{threshold_text}{fallback_text}"
    )
    if "hybrid" in metrics.get("score_type", ""):
        st.caption(
            "RRF score là điểm đồng thuận thứ hạng, không phải phần trăm độ tin cậy."
        )
    if metrics.get("retrieval_failed"):
        st.warning("Retrieval gặp lỗi; hệ thống đã chuyển sang safe refusal.")


def render_sources(sources: list[dict], retrieval_source: str) -> None:
    """Render the exact SearchResults used to generate an answer."""
    st.caption(f"Retrieval source: {retrieval_source}")
    if not sources:
        return

    with st.expander(f"Nguồn đã sử dụng ({len(sources)})"):
        for index, source in enumerate(sources, start=1):
            metadata = source["metadata"]
            title = metadata.get("title") or metadata.get("source") or "Không có tiêu đề"
            source_name = metadata.get("source") or "Không rõ nguồn"
            url = metadata.get("url")

            st.markdown(f"**[Document {index}] {title}**")
            if url:
                st.markdown(f"Nguồn: [{source_name}]({url})")
            else:
                st.write(f"Nguồn: {source_name}")
            score_label = {
                "hybrid": "RRF score",
                "dense": "Cosine similarity",
                "bm25": "BM25 score",
                "pageindex": "PageIndex score",
            }.get(source["retrieval_method"], "Score")
            st.caption(
                f"Method: {source['retrieval_method']} · "
                f"{score_label}: {float(source['score']):.4f} · "
                f"Chunk: {source['id']}"
            )
            preview = " ".join(source["content"].split())
            st.write(preview[:500] + ("…" if len(preview) > 500 else ""))
            if index < len(sources):
                st.divider()


if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.title("RAG Chatbot")
    st.caption("Hỏi đáp từ kho tài liệu pháp lý và bài viết du lịch.")
    strategy_label = st.selectbox("Retrieval strategy", list(STRATEGY_OPTIONS))
    strategy = STRATEGY_OPTIONS[strategy_label]
    top_k = st.slider("Số chunks", 3, 10, 5)
    score_threshold = st.slider(
        "Dense fallback threshold",
        min_value=0.0,
        max_value=1.0,
        value=min(1.0, max(0.0, float(SCORE_THRESHOLD))),
        step=0.05,
        disabled=strategy != "auto",
        help="Chỉ dùng trong chế độ Auto; so sánh với cosine score gốc của dense retrieval.",
    )
    st.caption(
        "Auto dùng Hybrid + RRF và chuyển sang PageIndex khi dense score thấp hơn threshold."
    )

st.title("Trợ lý Du lịch Việt Nam")
st.caption("Câu trả lời chỉ sử dụng bằng chứng từ các nguồn hiển thị bên dưới.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_metrics(message.get("metrics", {}))
            render_sources(
                message.get("sources", []),
                message.get("retrieval_source", "none"),
            )

query = st.chat_input("Nhập câu hỏi về du lịch Việt Nam...")

if query:
    st.session_state.messages.append({"role": "user", "content": query})

    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Đang tìm bằng chứng và tạo câu trả lời..."):
            try:
                result, metrics = generate_with_options(
                    query,
                    top_k=top_k,
                    strategy=strategy,
                    score_threshold=score_threshold,
                )
            except Exception:
                result = {
                    "answer": SAFE_REFUSAL,
                    "sources": [],
                    "retrieval_source": "none",
                }
                metrics = {}
        st.markdown(result["answer"])
        render_metrics(metrics)
        render_sources(result["sources"], result["retrieval_source"])

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": result["answer"],
            "sources": result["sources"],
            "retrieval_source": result["retrieval_source"],
            "metrics": metrics,
            "strategy": strategy,
        }
    )
