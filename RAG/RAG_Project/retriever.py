"""Retrieve relevant document chunks from the persisted Chroma database.

This module is the query-time half of the RAG pipeline:

    user question -> query embedding -> Chroma similarity search -> chunks

Documents must be ingested with ``vectordb.add_chunks_to_db()`` before they
can be retrieved.  The embedding model is loaded lazily and then reused by a
``Retriever`` instance, which is important when serving more than one query.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from typing import Any

from embedder import embed_query, load_embedding_model
from vectordb import get_or_create_collection, get_vector_db_client, query_db


class Retriever:
    """Query one persisted Chroma collection using the project's embedding model."""

    def __init__(
        self,
        persist_directory: str = "./vector_db",
        collection_name: str = "documents",
        model_name: str = "all-MiniLM-L6-v2",
        model: Any | None = None,
    ) -> None:
        """Open the collection without loading the embedding model yet.

        Pass ``model`` when the caller already has one loaded. Otherwise it is
        loaded only when the first non-empty database query is made.
        """
        client = get_vector_db_client(persist_directory)
        self.collection = get_or_create_collection(client, collection_name)
        self.model_name = model_name
        self._model = model

    @property
    def chunk_count(self) -> int:
        """Return the number of chunks currently available for retrieval."""
        return self.collection.count()

    def _get_model(self) -> Any:
        if self._model is None:
            self._model = load_embedding_model(self.model_name)
        return self._model

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        where: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return the most relevant stored chunks for ``query``.

        Args:
            query: A non-empty natural-language question.
            top_k: Maximum number of chunks to return.
            where: Optional Chroma metadata filter, for example
                ``{"file_extension": ".pdf"}``.

        Returns:
            A score-descending list of ``{"text", "metadata", "score"}``
            dictionaries. An empty collection returns an empty list.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        if where is not None and not isinstance(where, Mapping):
            raise TypeError("where must be a metadata mapping or None")

        available_chunks = self.chunk_count
        if available_chunks == 0:
            return []

        # Chroma rejects n_results greater than the collection size.
        query_embedding = embed_query(query.strip(), self._get_model())
        return query_db(
            self.collection,
            query_embedding,
            top_n=min(top_k, available_chunks),
            where=dict(where) if where is not None else None,
        )


def format_context(results: list[Mapping[str, Any]]) -> str:
    """Format retrieved results for the context section of a future LLM prompt.

    The source labels let the answer-generation stage cite the file and chunk
    that supplied each piece of evidence.
    """
    sections = []
    for rank, result in enumerate(results, start=1):
        metadata = result.get("metadata") or {}
        filename = metadata.get("filename", "unknown source")
        chunk_id = metadata.get("chunk_id", "unknown chunk")
        sections.append(
            f"[Source {rank}: {filename}, chunk {chunk_id}]\n{result['text']}"
        )
    return "\n\n".join(sections)


def main() -> None:
    """Provide a lightweight command-line check for the retrieval stage."""
    parser = argparse.ArgumentParser(description="Retrieve chunks from the RAG vector database.")
    parser.add_argument("query", help="Question to search for")
    parser.add_argument("--top-k", type=int, default=3, help="Number of chunks to return")
    parser.add_argument("--database", default="./vector_db", help="Chroma persistence directory")
    parser.add_argument("--collection", default="documents", help="Chroma collection name")
    args = parser.parse_args()

    retriever = Retriever(args.database, args.collection)
    results = retriever.retrieve(args.query, top_k=args.top_k)
    if not results:
        print("No chunks found. Ingest documents into the vector database first.")
        return

    for rank, result in enumerate(results, start=1):
        metadata = result["metadata"]
        print(
            f"--- Match {rank} (score: {result['score']:.3f}, "
            f"source: {metadata.get('filename', 'unknown')}, "
            f"chunk_id: {metadata.get('chunk_id', 'unknown')}) ---"
        )
        print(result["text"])
        print()


if __name__ == "__main__":
    main()
