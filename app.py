import streamlit as st
from dotenv import load_dotenv

from src.task10_generation import generate_with_citation


load_dotenv()

st.set_page_config(
    page_title="RAG Chatbot",
    page_icon="",
    layout="wide",
)

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.title("RAG Chatbot")
    st.caption("Thay mô tả theo đề tài của nhóm")
    top_k = st.slider("Số chunks", 3, 10, 5)

st.title("RAG Chatbot")
st.caption("Hỏi đáp dựa trên corpus du lịch Việt Nam và văn bản pháp lý liên quan.")


def render_sources(sources: list[dict]) -> None:
    """Render the retrieval evidence attached to a generated answer."""
    if not sources:
        return
    with st.expander("Nguồn tham khảo", expanded=False):
        for index, source in enumerate(sources, start=1):
            metadata = source["metadata"]
            title = metadata.get("title") or metadata["source"]
            score = float(source["score"])
            st.markdown(
                f"**[{index}] {title}**  \n"
                f"Nguồn: `{metadata['source']}` · "
                f"Phương thức: `{source['retrieval_method']}` · "
                f"Điểm: `{score:.3f}`"
            )
            if metadata.get("url"):
                st.markdown(f"URL: {metadata['url']}")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        render_sources(message.get("sources", []))

query = st.chat_input("Nhập câu hỏi...")

if query:
    st.session_state.messages.append({"role": "user", "content": query})

    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        result = generate_with_citation(query, top_k=top_k)
        answer = result["answer"]
        sources = result["sources"]
        st.markdown(answer)
        render_sources(sources)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "sources": sources,
        }
    )
