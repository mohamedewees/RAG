from vectordb import get_vector_db_client, get_or_create_collection

client = get_vector_db_client("./vector_db")
collection = get_or_create_collection(client, "documents")

collection.delete(
    where={
        "file_path": "/home/mohamed-ewees/Downloads/sepa_service_docs_confluence_export.pdf"
    }
)