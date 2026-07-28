"""
agent.py

The final stage of the pipeline: given a question, retrieve (and
optionally rerank) relevant chunks, build a grounded prompt, and
generate an answer using a local LLM via Ollama.

Fully offline: this reuses the exact same Ollama setup as
pdf_utils.describe_image_offline() -- same qwen3-vl:8b model, same
localhost endpoint. A vision-language model behaves like an ordinary
text model when no image is attached, so there's no need for a
separate model just for text generation.
"""

import requests


GROUNDED_ANSWER_PROMPT_TEMPLATE = """You are answering questions using ONLY the context provided below, taken from internal company documentation. Follow these rules strictly:

- Answer using only information found in the context below. Do not use outside knowledge, even if you know the answer some other way.
- If the context does not contain enough information to answer, say so plainly instead of guessing.
- When helpful, mention which source(s) in the context the answer came from.

Context:
{context}

Question: {question}

Answer:"""


def generate_answer(prompt, model="qwen3-vl:8b", ollama_host="http://localhost:11434", temperature=0.2):
    """
    Sends a text prompt to a locally running Ollama model and returns
    its response. No image involved here -- same endpoint used for
    image description in pdf_utils.py, just a plain text call.

    temperature is kept low (0.2) by default: grounded Q&A wants the
    model to stick close to the provided context rather than getting
    creative, unlike open-ended chat where more variation is welcome.

    Raises RuntimeError with setup guidance if Ollama isn't reachable,
    same pattern as pdf_utils.describe_image_offline().
    """
    try:
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature},
            },
            timeout=3000,
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"Could not reach Ollama at {ollama_host}. Is it installed and running? "
            f"(ollama serve, and make sure the model is pulled: ollama pull {model})"
        )

    return response.json()["response"].strip()


def ask(query, collection, embed_model, llm_model="qwen3-vl:8b",
        reranker_model=None, top_n=5, rerank_top_n=3, min_score=None,
        ollama_host="http://localhost:11434"):
    """
    The full query-time pipeline in one call:
    retrieve -> (optionally rerank) -> build a grounded prompt -> generate.

    Args:
        query: the user's question
        collection: from vectordb.get_or_create_collection()
        embed_model: from embedder.load_embedding_model()
        llm_model: the Ollama model to use for generation
        reranker_model: optional, from reranker.load_reranker_model().
            If provided, retrieved candidates get reranked before
            being used as context. If None, the top rerank_top_n
            embedding-ranked results are used directly -- reranking is
            an accuracy upgrade, not a hard requirement to get answers.
        top_n: how many chunks to retrieve initially (the wider net,
            before reranking)
        rerank_top_n: how many chunks actually get used as context --
            after reranking if a reranker_model was given, or just a
            straight slice of the embedding-ranked results otherwise
        min_score: optional relevance floor, passed through to retrieve()

    Returns:
        {
          "answer": "...",
          "sources": [...],   # the chunk records actually used as context
          "context": "...",   # the formatted context block, for debugging
        }

    Note the empty-knowledge-base case is handled explicitly: if
    nothing relevant is found, this returns a clear "I don't know"
    style answer WITHOUT calling the LLM at all -- there's no reason
    to spend time generating a response when there's no context to
    ground it in, and it avoids the model trying to answer from
    unrelated context just because something was retrieved.
    """
    from Retriever import retrieve, format_context

    results = retrieve(query, collection, embed_model, top_n=top_n, min_score=min_score)

    if reranker_model is not None:
        from Reranker import rerank
        results = rerank(query, results, reranker_model, top_n=rerank_top_n)
    elif rerank_top_n is not None:
        results = results[:rerank_top_n]

    if not results:
        return {
            "answer": "I couldn't find anything relevant to that question in the knowledge base.",
            "sources": [],
            "context": "",
        }

    context = format_context(results)
    prompt = GROUNDED_ANSWER_PROMPT_TEMPLATE.format(context=context, question=query)
    answer = generate_answer(prompt, model=llm_model, ollama_host=ollama_host)

    return {
        "answer": answer,
        "sources": results,
        "context": context,
    }


# --------------------------------------------------------------------------
# Try it out
# --------------------------------------------------------------------------

if __name__ == "__main__":
    from embedder import load_embedding_model
    from vectordb import get_vector_db_client, get_or_create_collection
    from Retriever import ingest_directory
    from Reranker import load_reranker_model

    print("Loading models (embedding + reranker)...")
    embed_model = load_embedding_model()
    reranker_model = load_reranker_model()

    client = get_vector_db_client(persist_directory="./vector_db")
    collection = get_or_create_collection(client, collection_name="documents")
    ingest_directory("/home/mohamed-ewees/Downloads/SEPA", collection, embed_model, chunk_size=600, overlap=1)

    query = "Descripe the mandate creation ?"
    print(f"\nQuery: {query}\n")

    result = ask(
        query, collection, embed_model,
        llm_model="qwen3-vl:8b",
        reranker_model=reranker_model,
        top_n=5, rerank_top_n=3,
        min_score=0.2,
    )

    print("=== Answer ===")
    print(result["answer"])
    print()
    print(f"=== Grounded in {len(result['sources'])} source(s) ===")
    for source in result["sources"]:
        print(f"  {source['metadata']['filename']} (score: {source['score']:.3f})")