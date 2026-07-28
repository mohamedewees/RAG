"""A small Streamlit interface for the local RAG pipeline.

Run from this directory with:
    streamlit run streamlit_app.py

The app uses the existing Chroma database in ``vector_db`` and a local
Ollama model for answer generation. Documents selected by the sidebar folder
path are ingested into that same persistent knowledge base.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from agent import ask
from embedder import load_embedding_model
from Retriever import ingest_directory
from vectordb import collection_count, get_or_create_collection, get_vector_db_client


PROJECT_DIR = Path(__file__).resolve().parent
DATABASE_DIR = PROJECT_DIR / "vector_db"
@st.cache_resource(show_spinner="Opening the knowledge base...")
def get_collection(database_path: str, collection_name: str):
    """Open the persistent Chroma collection once per Streamlit session."""
    client = get_vector_db_client(database_path)
    return get_or_create_collection(client, collection_name)


@st.cache_resource(show_spinner="Loading the embedding model...")
def get_embedding_model():
    """Load the embedding model once; it is reused for uploads and chat."""
    return load_embedding_model()


@st.cache_resource(show_spinner="Loading the reranker model...")
def get_reranker_model():
    from Reranker import load_reranker_model

    return load_reranker_model()


def add_document_directory(collection, directory: str, describe_images: bool) -> dict[str, int | str]:
    """Ingest every supported document in a user-selected directory."""
    directory_path = Path(directory).expanduser()
    if not directory_path.is_dir():
        raise ValueError("Enter the path to an existing folder.")

    return ingest_directory(
        str(directory_path),
        collection,
        get_embedding_model(),
        recursive=True,
        chunk_size=600,
        overlap=1,
        describe_images=describe_images,
    )


def show_sources(sources: list[dict]) -> None:
    """Render compact, inspectable citations beneath an assistant answer."""
    if not sources:
        return

    with st.expander(f"Sources ({len(sources)})"):
        for index, source in enumerate(sources, start=1):
            metadata = source.get("metadata", {})
            filename = metadata.get("filename", "Unknown file")
            chunk_id = metadata.get("chunk_id", "unknown")
            score = source.get("score", 0.0)
            st.markdown(f"**{index}. {filename}** — relevance: `{score:.3f}`  ")
            st.caption(f"Chunk: {chunk_id}")
            st.write(source.get("text", ""))


def main() -> None:
    st.set_page_config(page_title="Service Catalog", page_icon="📚", layout="wide")
    st.title("📚 Service Catalog")
    st.caption("Ask questions about your indexed documents. Answers are generated with your local Ollama model.")

    with st.sidebar:
        st.header("Knowledge base")
        collection_name = st.text_input("Collection name", value="documents")
        collection = get_collection(str(DATABASE_DIR), collection_name)
        st.metric("Indexed chunks", collection_count(collection))

        documents_directory = st.text_input(
            "Documents folder",
            placeholder="/path/to/your/documents",
            help="Indexes PDF, DOCX, TXT, and Markdown files in this folder and its subfolders.",
        )
        describe_images = st.checkbox("Extract text from PDF images (OCR)", value=False)

        if st.button("Ingest directory", type="primary", disabled=not documents_directory.strip()):
            try:
                with st.spinner("Parsing, embedding, and saving documents..."):
                    ingested = add_document_directory(collection, documents_directory, describe_images)
                successful = sum(1 for count in ingested.values() if isinstance(count, int))
                failed = len(ingested) - successful
                st.success(f"Ingested {successful} document(s).")
                if failed:
                    st.warning(f"{failed} document(s) could not be ingested; see the terminal for details.")
                st.rerun()
            except Exception as error:
                st.error(f"Could not ingest the document(s): {error}")

        st.divider()
        st.header("Answer settings")
        # model_name = st.text_input("Ollama model", value="qwen3-vl:8b")
        model_name = st.text_input("Ollama model", value="qwen2.5:3b")
        use_reranker = st.checkbox("Use reranker", value=False)
        top_n = st.slider("Retrieved chunks", min_value=1, max_value=10, value=5)
        rerank_top_n = st.slider("Chunks used in answer", min_value=1, max_value=5, value=3)
        min_score = st.slider("Minimum relevance", min_value=0.0, max_value=1.0, value=0.2, step=0.05)

        if st.button("Clear chat"):
            st.session_state.messages = []
            st.rerun()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                show_sources(message.get("sources", []))

    question = st.chat_input("Ask a question about your documents")
    if not question:
        return

    if collection_count(collection) == 0:
        st.warning("Your knowledge base is empty. Add and ingest at least one document first.")
        return

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Searching the knowledge base and drafting an answer..."):
                reranker_model = get_reranker_model() if use_reranker else None
                result = ask(
                    question,
                    collection,
                    get_embedding_model(),
                    llm_model=model_name,
                    reranker_model=reranker_model,
                    top_n=top_n,
                    rerank_top_n=rerank_top_n,
                    min_score=min_score,
                )
            st.markdown(result["answer"])
            show_sources(result["sources"])
            st.session_state.messages.append(
                {"role": "assistant", "content": result["answer"], "sources": result["sources"]}
            )
        except Exception as error:
            message = f"I couldn't generate an answer: {error}"
            st.error(message)
            st.session_state.messages.append({"role": "assistant", "content": message, "sources": []})


if __name__ == "__main__":
    main()
