import os
from pathlib import Path
from typing import List, Dict
import hashlib

class TextDocumentParser:
    """Parse text files for RAG system ingestion."""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
    def parse_file(self, file_path: str) -> Dict:
        """Parse a text file and extract content with metadata."""
        path = Path(file_path)
        
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract metadata
        metadata = {
            'filename': path.name,
            'file_path': str(path.absolute()),
            'file_size': path.stat().st_size,
            'file_extension': path.suffix,
            'document_id': self._generate_doc_id(file_path),
            'char_count': len(content),
            'word_count': len(content.split())
        }
        
        return {
            'content': content,
            'metadata': metadata
        }
    
    def _generate_doc_id(self, file_path: str) -> str:
        """Generate a unique document ID based on file path."""
        return hashlib.md5(file_path.encode()).hexdigest()
    
    def chunk_text(self, text: str) -> List[Dict]:
        
        """Split text into overlapping chunks for RAG processing."""
        chunks = []
        start = 0
        chunk_id = 0
        
        while start < len(text):
            # Calculate initial end position
            end = start + self.chunk_size
            
            # Try to break at sentence or word boundary
            if end < len(text):
                # Look for sentence endings
                sentence_ends = ['.', '!', '?', '\n\n']
                best_break = end
                
                # Search backwards for sentence ending
                for i in range(end, max(start + self.chunk_size - 100, start), -1):
                    if i < len(text) and text[i] in sentence_ends:
                        best_break = i + 1
                        break
                
                # If no sentence break found, try word boundary
                if best_break == end:
                    for i in range(end, max(start + self.chunk_size - 50, start), -1):
                        if i < len(text) and text[i].isspace():
                            best_break = i
                            break
                
                end = best_break
            
            # Extract chunk
            chunk_text = text[start:end].strip()
            
            if chunk_text:  # Only add non-empty chunks
                chunks.append({
                    'chunk_id': chunk_id,
                    'text': chunk_text,
                    'start_char': start,
                    'end_char': end,
                    'chunk_length': len(chunk_text)
                })
                chunk_id += 1
            
            # Move start position with overlap
            start = end - self.chunk_overlap if end < len(text) else end
            
        return chunks
    
    def process_document(self, file_path: str) -> List[Dict]:
        """Complete pipeline: parse file and create chunks."""
        # Parse the document
        doc_data = self.parse_file(file_path)
        
        # Chunk the content
        chunks = self.chunk_text(doc_data['content'])
        
        # Add document metadata to each chunk
        for chunk in chunks:
            chunk['document_metadata'] = doc_data['metadata']    
        return chunks  
    
if __name__ == "__main__":
    # Initialize parser with custom settings
    parser = TextDocumentParser(chunk_size=500, chunk_overlap=100)
        
    # Create sample document
    #sample_text = """Introduction to RAG Systems 
    #Retrieval-Augmented Generation (RAG) is a powerful technique..."""
        
    #with open('sample_doc.txt', 'w', encoding='utf-8') as f:
    #    f.write(sample_text)
        
    # Process document
    chunks = parser.process_document('sample_doc.txt')
        
    # Display results
    print(f"Document: {chunks[0]['document_metadata']['filename']}")
    print(f"Total chunks: {len(chunks)}")
        
    for chunk in chunks[:3]:
        print(f"\nChunk {chunk['chunk_id']}:")
        print(f"Length: {chunk['chunk_length']} chars")
        print(f"Text: {chunk['text'][:150]}...")