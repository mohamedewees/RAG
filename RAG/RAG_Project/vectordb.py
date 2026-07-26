"""
vectordb.py

Persists chunk embeddings to disk (via ChromaDB) so you don't have to
re-embed every document every time you run the pipeline. Once a
document's chunks are stored, future runs just query the existing
database -- new documents get added incrementally alongside it.

Fully offline: ChromaDB is an embedded, local database (like SQLite,
not a client-server system you connect to over a network). Everything
here reads/writes to a folder on disk -- zero network calls.
"""

import chromadb


def get_vector_db_client(persist_directory="./vector_db"):
    """
    Opens (or creates) a persistent ChromaDB client backed by a folder
    on disk. Call this once per program run and reuse the client --
    it's the same idea as loading the embedding model once in
    embedder.py rather than reloading it on every call.
    """
    return chromadb.PersistentClient(path=persist_directory)


def get_or_create_collection(client, collection_name="documents"):
    """
    A "collection" is ChromaDB's term for a table -- a named group of
    chunks you can query together. Using get_or_create (rather than
    create) means this is safe to call every run: the first run creates
    it, every run after that just reopens the existing one.
    """
    return client.get_or_create_collection(name=collection_name)


def add_chunks_to_db(collection, chunk_records, chunk_embeddings,
                     replace_existing_content=True):
    """
    Stores chunks + their embeddings + their metadata in the collection.

    Args:
        collection: from get_or_create_collection()
        chunk_records: list of {"text": ..., "metadata": ...} dicts
            (the output of chunker.chunk_document())
        chunk_embeddings: embeddings from embedder.embed_chunks(),
            aligned by position with chunk_records

    Why chunk_id as the database ID? It's already globally unique
    (document_id + chunk_index, from chunker.py) -- reusing it here
    means re-adding the same document twice just overwrites the same
    rows instead of creating duplicates.

    When ``replace_existing_content`` is true (the default), chunks from an
    earlier copy of the same file are deleted first.  This matters when a file
    is moved: its path-based ``chunk_id`` changes, but its SHA-256
    ``content_hash`` does not.
    """
    ids = [record["metadata"]["chunk_id"] for record in chunk_records]
    documents = [record["text"] for record in chunk_records]
    metadatas = [record["metadata"] for record in chunk_records]

    # Chroma wants embeddings as plain lists, not numpy arrays
    embeddings = [list(map(float, vec)) for vec in chunk_embeddings]

    if replace_existing_content and chunk_records:
        content_hashes = {record["metadata"].get("content_hash")
                          for record in chunk_records}
        if None in content_hashes or len(content_hashes) != 1:
            raise ValueError(
                "All chunks must have one content_hash. "
                "Create them with chunker.chunk_document()."
            )

        # Deleting by metadata happens before the upsert, so a moved/copied
        # file replaces every old copy while the new chunks are still added.
        collection.delete(where={"content_hash": content_hashes.pop()})

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )


def query_db(collection, query_embedding, top_n=3, where=None):
    """
    Finds the most relevant stored chunks for a query embedding.

    Args:
        collection: from get_or_create_collection()
        query_embedding: from embedder.embed_query()
        top_n: how many results to return
        where: optional metadata filter, e.g. {"file_extension": ".pdf"}
            to only search within PDFs -- this is the main practical
            advantage over the plain in-memory search in embedder.py:
            you can narrow the search using metadata without having to
            loop through everything in Python yourself.

    Returns:
        A list of dicts, highest similarity first:
            [{"text": ..., "metadata": ..., "score": 0.83}, ...]
        Same shape as embedder.find_most_relevant_chunks(), so calling
        code doesn't need to care whether results came from the
        in-memory version or the persisted database.
    """
    results = collection.query(
        query_embeddings=[list(map(float, query_embedding))],
        n_results=top_n,
        where=where,
    )

    formatted = []
    # Chroma returns parallel lists (one per query -- we only sent one)
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for text, metadata, distance in zip(documents, metadatas, distances):
        # Chroma's default distance is squared L2 (smaller = more similar),
        # not cosine similarity (bigger = more similar) -- convert so the
        # output shape/meaning matches embedder.find_most_relevant_chunks()
        similarity_score = 1 / (1 + distance)
        formatted.append({
            "text": text,
            "metadata": metadata,
            "score": similarity_score,
        })

    return formatted


def collection_count(collection):
    """How many chunks are currently stored -- handy for sanity checks."""
    return collection.count()


# --------------------------------------------------------------------------
# Try it out
# --------------------------------------------------------------------------

if __name__ == "__main__":
    from parser import read_document
    from chunker import chunk_document
    from embedder import load_embedding_model, embed_chunks, embed_query

    file_path = r"/home/mohamed-ewees/Downloads/sepa_service_docs_confluence_export.pdf"

    text = read_document(file_path)
    chunk_records = chunk_document(file_path, text, chunk_size=600, overlap=1)
    print(f"{len(chunk_records)} chunks from {file_path}")

    print("Loading embedding model...")
    model = load_embedding_model()
    chunk_embeddings = embed_chunks(chunk_records, model)

    print("Connecting to vector database...")
    client = get_vector_db_client(persist_directory="./vector_db")
    collection = get_or_create_collection(client, collection_name="documents")

    add_chunks_to_db(collection, chunk_records, chunk_embeddings)
    print(f"Stored. Collection now has {collection_count(collection)} chunks total.\n")

    query = "Descripe the mandate creation ?"
    print(f"Query: {query}\n")

    query_embedding = embed_query(query, model)
    results = query_db(collection, query_embedding, top_n=2)

    for rank, result in enumerate(results, start=1):
        print(f"--- Match {rank} (score: {result['score']:.3f}, "
              f"chunk_id: {result['metadata']['chunk_id']}) ---")
        print(result["text"])
        print()
