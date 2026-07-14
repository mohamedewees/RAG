import re

# 1. File Reading Method
def read_file(fullPath):
    with open(fullPath,'r',encoding='utf-8') as f:
        text = f.read().strip()
        return text

# print(read_file(r'D:\programming\VS-Code_Workspace\RAG-Course\text_parsing\Sample_text.txt'))

############################################################################################################################

# 2. Chunking Methods

# 2.a Fixed size chunking
def fixed_size_chunking(text, chunk_size = 200):
    return [text[i:i+chunk_size] for i in range(0,len(text),chunk_size)]

# 2.b Chunking with overlap
def chunk_with_overlap(text,chunk_size=200,overlap = 50):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

# 2.c Sentence based Chunking
def sentence_chunking(text, max_sentences = 3): 
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks = []
    for i in range(0,len(sentences),max_sentences):
        chunk = ' '.join(sentences[i: i + max_sentences])
        chunks.append(chunk)
    return chunks

# 2.d Paragraoh chunking
def paragraph_chunk(text):
    paragraph = re.split(r'\n\s*\n', text.strip())
    return [p.strip() for p in paragraph if p.strip()]

############################################################################################################################
# 3. Display Helper function
def print_chunks(label,chunks):
    print(f"\n{'='*50}")
    print(f"{label} -> {len(chunks)} chunks")
    print(f"\n{'='*50}")
    for i,chunk in enumerate(chunks,1):
        print(f"\n[chunk {i}]\n{chunk}")
#############################################################################################################################

# 4. Main Function
def main():
    filepath = r'C:\Users\EweesM\OneDrive - Vodafone Group\Documents\programming\RAG\text_parsing\Sample_text.txt'
    
    # Step 1: Read the file
    text = read_file(filepath)
    print(f"File Loaded -- {len(text)} Characters\n")

    # Step 2: Run all 4 chuniking methods
    print_chunks("Fixed Size", fixed_size_chunking(text,chunk_size=200))
    print_chunks("Fixed + Overlap", chunk_with_overlap(text,chunk_size=200,overlap=50))
    print_chunks("Sentence_Based", sentence_chunking(text, max_sentences=3))
    print_chunks("Paragraph-Based", paragraph_chunk(text))

if __name__ == "__main__":
    main()
