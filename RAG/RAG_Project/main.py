from parser import read_document
from chunker import chunk_document , chunk_text
 
if __name__ == "__main__":
    file_path = r"/home/mohamed-ewees/Downloads/sepa_service_docs_confluence_export.pdf"
 
    # one call instead of read_document() + chunk_text() separately
    # chunks = load_and_chunk(file_path, chunk_size=200, overlap=50)
 
    text = read_document(file_path)
    chunks = chunk_text(text, chunk_size=500, overlap_sentences=1)
 
 
 
    print(f"Loaded and chunked {file_path} into {len(chunks)} chunks:\n")
 
    for i, chunk in enumerate(chunks):
        print(f"--- Chunk {i} ({len(chunk)} chars) ---")
        print(chunk)
        print()
 
    # print("\n=== Same thing, but with metadata attached ===\n")
    # chunk_records = chunk_document(file_path, text, chunk_size=200, overlap=1)
    # for record in chunk_records:
    #     print(f"--- {record['metadata']['chunk_id']} ---")
    #     print(f"From: {record['metadata']['filename']}")
    #     print(record["text"][:80] + "...")
    #     print()
