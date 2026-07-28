"""
cli.py

A small interactive command-line interface for asking questions,
instead of hardcoding a query and re-running the script every time.

Usage:
    python cli.py

Assumes documents have ALREADY been ingested (via retriever.py's
ingest_document / ingest_documents / ingest_directory, run separately
beforehand) -- this script only handles the QUESTION-ASKING side. That
split matters: ingestion is a one-time-per-document cost, asking
questions is something you do repeatedly, so they're kept as separate
steps rather than re-ingesting on every run of this file.
"""

from embedder import load_embedding_model
from vectordb import get_vector_db_client, get_or_create_collection, collection_count
from Reranker import load_reranker_model
from agent import ask


def print_answer(result):
    """Displays one answer + its sources in a readable format."""
    print()
    print(result["answer"])
    print()

    if result["sources"]:
        print("Sources:")
        for source in result["sources"]:
            filename = source["metadata"].get("filename", "unknown")
            score = source["score"]
            print(f"  - {filename} (relevance: {score:.2f})")
    print()


def run_cli(persist_directory="./vector_db", collection_name="documents",
            llm_model="qwen3-vl:8b", top_n=5, rerank_top_n=3, min_score=0.2):
    """
    The interactive loop: load everything ONCE (models are the slow
    part -- loading them per-question would make every single question
    painfully slow), then keep asking for input until the user quits.
    """
    print("Loading embedding model...")
    embed_model = load_embedding_model()

    print("Loading reranker model...")
    reranker_model = load_reranker_model()

    client = get_vector_db_client(persist_directory=persist_directory)
    collection = get_or_create_collection(client, collection_name=collection_name)

    chunk_count = collection_count(collection)
    if chunk_count == 0:
        print()
        print("The knowledge base is empty -- no documents have been ingested yet.")
        print("Run this first, then come back and start this CLI again:")
        print()
        print("  from retriever import ingest_directory")
        print("  from embedder import load_embedding_model")
        print("  from vectordb import get_vector_db_client, get_or_create_collection")
        print("  ")
        print("  model = load_embedding_model()")
        print("  client = get_vector_db_client()")
        print("  collection = get_or_create_collection(client)")
        print("  ingest_directory('./company_docs', collection, model)")
        print()
        return

    print(f"\nReady. {chunk_count} chunks loaded from the knowledge base.")
    print("Ask a question, or type 'quit' / 'exit' to stop.\n")

    while True:
        try:
            query = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            # Ctrl+C or Ctrl+D -- exit cleanly instead of an ugly traceback
            print("\nGoodbye.")
            break

        if not query:
            continue  # empty input -- just re-prompt, don't waste a model call

        if query.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        print("Thinking... (this can take a while on CPU-only hardware)")

        try:
            result = ask(
                query, collection, embed_model,
                llm_model=llm_model,
                reranker_model=reranker_model,
                top_n=top_n, rerank_top_n=rerank_top_n,
                min_score=min_score,
            )
            print_answer(result)
        except RuntimeError as e:
            # e.g. Ollama not running, or timed out -- a real problem worth
            # showing clearly, but not a reason to crash the whole session.
            # The user can fix Ollama and just try again without restarting.
            print(f"\nSomething went wrong: {e}\n")


if __name__ == "__main__":
    run_cli()