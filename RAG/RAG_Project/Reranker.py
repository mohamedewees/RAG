"""
reranker.py

Refines retriever.py's initial candidate list using a CROSS-ENCODER --
a small model that looks at the query and a chunk TOGETHER (not as two
separately-computed vectors) to judge relevance more precisely.

Why do we need this on top of retrieve()? Embedding-based retrieval
(a "bi-encoder": query and chunks embedded separately, then compared
via cosine similarity) is fast enough to search thousands of chunks,
but it's an approximation -- the query and chunk never actually "see"
each other, so it sometimes ranks a superficially-similar-but-wrong
chunk above the actually-correct one. A cross-encoder is slower (it
has to run once per candidate, at query time -- it can't be
precomputed and indexed the way embeddings can) but meaningfully more
accurate. The standard pattern: retrieve a wider net cheaply (e.g.
top 10 via embeddings), then rerank that smaller set precisely (down
to top 3-5) before it goes to generation.

Fully offline: like the embedding model, the cross-encoder downloads
once (a few hundred MB) and runs entirely locally after that -- no
Ollama, no API, just another local sentence-transformers model.
"""

from sentence_transformers import CrossEncoder


def load_reranker_model(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2"):
    """
    Loads the cross-encoder model. Same pattern as
    embedder.load_embedding_model() -- load once, reuse everywhere.

    "ms-marco-MiniLM-L-6-v2" is a small, fast, well-established default
    for reranking -- trained specifically on query-passage relevance,
    similar size/speed tradeoff to all-MiniLM-L6-v2 used for embeddings.
    """
    return CrossEncoder(model_name)


def rerank(query, results, reranker_model, top_n=None):
    """
    Re-scores and re-sorts retrieved chunks using the cross-encoder.

    Args:
        query: the original question, plain text
        results: output of retriever.retrieve() -- list of
            {"text", "metadata", "score"} dicts
        reranker_model: from load_reranker_model()
        top_n: how many to keep after reranking (None = keep all,
            just re-sorted in the new order)

    Returns:
        Same shape as the input, but re-sorted by cross-encoder
        relevance. The original embedding-based score is preserved
        under "embedding_score" in case you want to compare the two;
        "score" is overwritten with the cross-encoder's score, so
        anything downstream (format_context, etc.) keeps working
        unmodified -- it just sees a more accurate "score" now.
    """
    if not results:
        return results

    pairs = [(query, r["text"]) for r in results]
    cross_scores = reranker_model.predict(pairs)

    reranked = []
    for result, cross_score in zip(results, cross_scores):
        reranked.append({
            **result,
            "embedding_score": result["score"],
            "score": float(cross_score),
        })

    reranked.sort(key=lambda r: r["score"], reverse=True)

    if top_n is not None:
        reranked = reranked[:top_n]

    return reranked


# --------------------------------------------------------------------------
# Try it out
# --------------------------------------------------------------------------

if __name__ == "__main__":
    from embedder import load_embedding_model
    from vectordb import get_vector_db_client, get_or_create_collection
    from Retriever import ingest_document, retrieve, format_context

    print("Loading embedding + reranker models...")
    embed_model = load_embedding_model()
    reranker_model = load_reranker_model()

    client = get_vector_db_client(persist_directory="./vector_db")
    collection = get_or_create_collection(client, collection_name="documents")
    ingest_document("sample.txt", collection, embed_model, chunk_size=600, overlap=1)

    query = "Descripe the mandate creation ?"
    print(f"\nQuery: {query}\n")

    initial_results = retrieve(query, collection, embed_model, top_n=5, min_score=0.0)
    print(f"Retrieved {len(initial_results)} candidates (embedding-based ranking):")
    for r in initial_results:
        print(f"  embedding score {r['score']:.3f}  {r['metadata']['chunk_id']}")

    reranked_results = rerank(query, initial_results, reranker_model, top_n=3)
    print(f"\nAfter reranking, top {len(reranked_results)}:")
    for r in reranked_results:
        print(f"  cross-encoder score {r['score']:.3f} "
              f"(was embedding score {r['embedding_score']:.3f})  {r['metadata']['chunk_id']}")

    print("\n=== Final context passed to generation ===\n")
    print(format_context(reranked_results))