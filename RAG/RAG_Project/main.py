from parser import read_document
from chunker import chunk_document , chunk_text

if __name__ == "__main__":
    file_path = r"/home/mohamed-ewees/Downloads/My CV-20260716T121707Z-1-001/My CV/DevOps/AI generated/Mohammed_Ewees.docx"
 
    # one call instead of read_document() + chunk_text() separately
    # chunks = load_and_chunk(file_path, chunk_size=200, overlap=50)

    text = read_document(file_path)
    chunks = chunk_text(text)



    print(f"Loaded and chunked {file_path} into {len(chunks)} chunks:\n")
 
    for i, chunk in enumerate(chunks):
        print(f"--- Chunk {i} ({len(chunk)} chars) ---")
        print(chunk)
        print()
 
    print("\n=== Same thing, but with metadata attached ===\n")
    chunk_records = chunk_document(file_path,text, chunk_size=200, overlap=50)
    for record in chunk_records:
        print(f"--- {record['metadata']['chunk_id']} ---")
        print(f"From: {record['metadata']['filename']}")
        print(record["text"][:80] + "...")
        print()