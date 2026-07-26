"""
embedder.py

Turns chunks (from chunker.py's chunk_document()) into embeddings --
numeric vectors that capture MEANING, not just keywords -- and finds
the most relevant chunks for a given question.

Fully offline: sentence-transformers models run locally once downloaded.
The first call to load_embedding_model() needs internet ONCE to fetch
the model (a few hundred MB); every call after that is pure local
computation, no network involved.
"""

import numpy as np
from sentence_transformers import SentenceTransformer


def load_embedding_model(model_name="all-MiniLM-L6-v2"):
    """
    Loads the embedding model. Do this ONCE and reuse the same model
    object for every embed/search call -- loading it is the slow part
    (reading weights off disk), so reloading per-call would make
    everything unnecessarily slow.

    "all-MiniLM-L6-v2" is a good default: small (~80MB), fast even on
    CPU, and good enough quality for most document search use cases.
    """
    return SentenceTransformer(model_name)


def embed_chunks(chunk_records, model):
    """
    Embeds every chunk in a list of chunk records (the output of
    chunker.chunk_document()).

    Args:
        chunk_records: list of {"text": ..., "metadata": ...} dicts
        model: an embedding model from load_embedding_model()

    Returns:
        A numpy array of shape (num_chunks, embedding_dimension).
        Row i corresponds to chunk_records[i] -- the two stay aligned
        by position, so you can zip() them together later.
    """
    texts = [record["text"] for record in chunk_records]
    return model.encode(texts)


def embed_query(query, model):
    """Embeds a single piece of text (typically a user's question)."""
    return model.encode(query)


def cosine_similarity(vec_a, vec_b):
    """
    Measures how similar two vectors are, from -1 (opposite) to 1
    (identical direction). This is what lets us rank chunks by MEANING
    rather than exact keyword overlap.
    """
    dot_product = np.dot(vec_a, vec_b)
    magnitude_a = np.linalg.norm(vec_a)
    magnitude_b = np.linalg.norm(vec_b)
    return float(dot_product / (magnitude_a * magnitude_b))


def find_most_relevant_chunks(query, chunk_records, chunk_embeddings, model, top_n=3):
    """
    Given a question, finds the chunks whose meaning is closest to it.

    Args:
        query: the question, as plain text
        chunk_records: the list of {"text", "metadata"} dicts (same
            list, same order, used to build chunk_embeddings)
        chunk_embeddings: embeddings from embed_chunks(chunk_records, model)
        model: the embedding model (used to embed the query the same way)
        top_n: how many top matches to return

    Returns:
        A list of dicts, highest similarity first:
            [{"text": ..., "metadata": ..., "score": 0.83}, ...]
        The metadata is carried through untouched, so a caller always
        knows which document and chunk a result came from -- not just
        the matching text.
    """
    query_embedding = embed_query(query, model)

    scored = []
    for record, embedding in zip(chunk_records, chunk_embeddings):
        score = cosine_similarity(query_embedding, embedding)
        scored.append((score, record))

    scored.sort(key=lambda pair: pair[0], reverse=True)

    results = []
    for score, record in scored[:top_n]:
        results.append({
            "text": record["text"],
            "metadata": record["metadata"],
            "score": score,
        })
    return results


# --------------------------------------------------------------------------
# Try it out
# --------------------------------------------------------------------------

if __name__ == "__main__":
    from parser import read_document
    from chunker import chunk_document

    file_path = r"/home/mohamed-ewees/Downloads/sepa_service_docs_confluence_export.pdf"

    text = read_document(file_path)
    chunk_records = chunk_document(file_path, text, chunk_size=600, overlap=1)
    print(f"{len(chunk_records)} chunks from {file_path}\n")

    print("Loading embedding model (first run downloads it, be patient)...")
    model = load_embedding_model()

    chunk_embeddings = embed_chunks(chunk_records, model)
    print(f"Created {len(chunk_embeddings)} embeddings, "
          f"each with {chunk_embeddings.shape[1]} dimensions\n")

    # query = "What does SEPA do?"
    # query = "What are the prerequisits for the deployment?"
    query = "Descripe the mandate creation ?"
    print(f"Query: {query}\n")

    results = find_most_relevant_chunks(query, chunk_records, chunk_embeddings, model, top_n=2)
    for rank, result in enumerate(results, start=1):
        print(f"--- Match {rank} (score: {result['score']:.3f}, "
              f"chunk_id: {result['metadata']['chunk_id']}) ---")
        print(result["text"])
        print()