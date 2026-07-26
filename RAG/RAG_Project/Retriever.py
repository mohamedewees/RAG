"""
retriever.py

The query-time half of the RAG pipeline: given a plain-text question,
find the most relevant chunks already stored in the vector database.

This ties embedder.py (turning the QUESTION into a vector) together
with vectordb.py (searching already-stored vectors) into a single
call, so later stages (reranker.py, agent.py) don't need to know
anything about embedding models or database internals -- just
"give me a question, get back relevant chunks."
"""

from embedder import embed_query
from vectordb import query_db


def retrieve(query, collection, model, top_n=5, where=None, min_score=None):
    """
    Finds the most relevant stored chunks for a question.

    Args:
        query: the user's question, plain text
        collection: a ChromaDB collection, from
            vectordb.get_or_create_collection()
        model: the embedding model, from embedder.load_embedding_model()
        top_n: how many chunks to return at most
        where: optional metadata filter, e.g. {"file_extension": ".pdf"}
            to only search within PDFs
        min_score: optional similarity floor (0-1). Results scoring
            below this get dropped. Why this matters: if someone asks
            a question your documents genuinely don't cover, the
            search will still return its "closest" matches -- they'll
            just be weakly related, not actually relevant. Without a
            floor, those weak matches get treated as real context and
            can mislead whatever generates the final answer. Leave as
            None to disable this and always return top_n results
            regardless of how weak they are.

    Returns:
        list of {"text", "metadata", "score"} dicts, highest score
        first -- same shape as vectordb.query_db() and
        embedder.find_most_relevant_chunks(), so this is a drop-in
        regardless of which backing search was used before.
    """
    query_embedding = embed_query(query, model)
    results = query_db(collection, query_embedding, top_n=top_n, where=where)

    if min_score is not None:
        results = [r for r in results if r["score"] >= min_score]

    return results


def format_context(results, max_chunks=None):
    """
    Formats retrieved chunks into a single text block suitable for
    dropping into an LLM prompt later (agent.py). Each chunk is
    labeled with its source filename so both the model and the end
    user can see where an answer's grounding actually came from,
    rather than presenting retrieved text as if it came from nowhere.

    Args:
        results: output of retrieve()
        max_chunks: optionally cap how many chunks get included, even
            if more were retrieved (useful once you add a reranker and
            only want to pass the best few through to generation)
    """
    if max_chunks is not None:
        results = results[:max_chunks]

    if not results:
        return "No relevant context was found in the knowledge base."

    blocks = []
    for i, result in enumerate(results, start=1):
        filename = result["metadata"].get("filename", "unknown source")
        blocks.append(f"[Source {i}: {filename}]\n{result['text']}")

    return "\n\n".join(blocks)


# --------------------------------------------------------------------------
# Ingestion helpers -- for adding MORE than one file
# --------------------------------------------------------------------------

def ingest_document(file_path, collection, model, chunk_size=600, overlap=1,
                     describe_images=True, image_backend="ocr"):
    """
    Runs one file through the full parse -> chunk -> embed -> store
    pipeline and adds it to the vector database.

    Safe to call repeatedly, including after a file has been moved or copied.
    ``add_chunks_to_db()`` deletes chunks with the same content hash before
    upserting the new chunks, so only one copy of identical content remains.

    Returns the number of chunks added.
    """
    from parser import read_document
    from chunker import chunk_document
    from embedder import embed_chunks
    from vectordb import add_chunks_to_db

    text = read_document(file_path, describe_images=describe_images, image_backend=image_backend)
    chunk_records = chunk_document(file_path, text, chunk_size=chunk_size, overlap=overlap)
    chunk_embeddings = embed_chunks(chunk_records, model)
    add_chunks_to_db(collection, chunk_records, chunk_embeddings)
    return len(chunk_records)


def ingest_documents(file_paths, collection, model, **kwargs):
    """
    Ingests a LIST of files into the same collection, one at a time.
    All of them end up searchable together -- retrieve() doesn't care
    which file a chunk came from unless you filter for it with `where`.

    A failure on one file (unsupported format, corrupt PDF, etc.)
    doesn't stop the rest of the batch -- it's reported and skipped,
    since one bad file in a folder of hundreds shouldn't block
    everything else from being ingested.

    Returns a dict mapping file_path -> number of chunks added (or the
    error message, if that file failed).
    """
    results = {}
    for file_path in file_paths:
        try:
            count = ingest_document(file_path, collection, model, **kwargs)
            results[file_path] = count
            print(f"  OK   {file_path}: {count} chunks")
        except Exception as e:
            results[file_path] = f"FAILED: {e}"
            print(f"  FAIL {file_path}: {e}")
    return results


def ingest_directory(dir_path, collection, model, recursive=True, **kwargs):
    """
    Ingests every supported file (.txt, .md, .pdf, .docx) found in a
    directory -- the natural way to point this at an entire folder of
    company documentation instead of listing files one by one.
    """
    import os

    supported_extensions = {".txt", ".md", ".pdf", ".docx"}
    file_paths = []

    if recursive:
        for root, _, files in os.walk(dir_path):
            for fname in files:
                if os.path.splitext(fname)[1].lower() in supported_extensions:
                    file_paths.append(os.path.join(root, fname))
    else:
        for fname in os.listdir(dir_path):
            full_path = os.path.join(dir_path, fname)
            if os.path.isfile(full_path) and os.path.splitext(fname)[1].lower() in supported_extensions:
                file_paths.append(full_path)

    print(f"Found {len(file_paths)} supported file(s) in {dir_path}")
    return ingest_documents(file_paths, collection, model, **kwargs)


# --------------------------------------------------------------------------
# Try it out
# --------------------------------------------------------------------------

if __name__ == "__main__":
    from embedder import load_embedding_model
    from vectordb import get_vector_db_client, get_or_create_collection

    print("Loading embedding model...")
    model = load_embedding_model()

    client = get_vector_db_client(persist_directory="./vector_db")
    collection = get_or_create_collection(client, collection_name="documents")

    # --- ingest MULTIPLE files into the same collection ---
    # file_paths = [r"/home/mohamed-ewees/Downloads/SEPA"]
    # print(f"\nIngesting {len(file_paths)} files:")
    # ingest_documents(file_paths, collection, model, chunk_size=600, overlap=1)

    # --- or ingest a whole folder at once ---
    ingest_directory("/home/mohamed-ewees/Downloads/SEPA", collection, model, chunk_size=600, overlap=1)

    # --- query time: searches across ALL ingested documents together ---
    query = "Descripe the mandate creation ?"
    print(f"\nQuery: {query}\n")

    results = retrieve(query, collection, model, top_n=3, min_score=0.2)

    print(f"{len(results)} result(s) above the relevance floor:\n")
    for result in results:
        print(f"--- {result['metadata']['chunk_id']} "
              f"(score: {result['score']:.3f}, from: {result['metadata']['filename']}) ---")
        print(result["text"])
        print()

    print("=== Formatted for an LLM prompt ===\n")
    print(format_context(results))
