import re
import hashlib
from pathlib import Path
 
 
SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
 
 
def split_into_sentences(paragraph):
    """Split a paragraph into sentences."""
    return [s.strip() for s in SENTENCE_PATTERN.split(paragraph) if s.strip()]
 
 
def _hard_split(text, max_len, overlap=50):
    """
    Safety-net splitter: force-splits a piece of text that's too long to
    fit in a chunk on its own, using a plain character sliding window
    (no sentence-awareness -- by the time we get here, sentence-awareness
    has already failed to produce something small enough).
    """
    pieces = []
    start = 0
    while start < len(text):
        end = min(start + max_len, len(text))
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(text):
            break
        start = end - overlap
    return pieces
 
 
def chunk_text(text, chunk_size=500, overlap_sentences=1):
    """
    Paragraph-aware, sentence-aware chunking with a guaranteed max size.
 
    Parameters
    ----------
    chunk_size : int
        Maximum characters per chunk. This is a HARD ceiling -- no
        chunk will exceed it, even for pathological input.
    overlap_sentences : int
        Number of pieces (sentences, or whole short paragraphs) to
        repeat at the start of the next chunk, for context continuity
        across the boundary.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap_sentences < 0:
        raise ValueError("overlap_sentences cannot be negative")
 
    chunks = []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
 
    current_pieces = []
    current_length = 0
 
    def flush(carry_overlap=True):
        """Emit the current chunk and optionally carry overlap forward."""
        nonlocal current_pieces, current_length
        if not current_pieces:
            return
        chunks.append(" ".join(current_pieces))
 
        if carry_overlap and overlap_sentences:
            current_pieces = current_pieces[-overlap_sentences:]
            current_length = sum(len(p) + 1 for p in current_pieces)
        else:
            current_pieces = []
            current_length = 0
 
    def add_piece(piece):
        """
        Add a single piece (a paragraph or a sentence), flushing first
        if it wouldn't fit. Checks fit TWICE: once before flushing, and
        once more after carrying the overlap forward -- if the carried
        overlap alone is already close to chunk_size, a plain flush()
        isn't enough on its own to make room, so we drop the overlap
        for this one boundary rather than let the chunk grow past the
        limit. Without this second check, a chunk could exceed
        chunk_size by however long the carried-over overlap was.
        """
        nonlocal current_pieces, current_length
 
        if current_pieces and current_length + len(piece) + 1 > chunk_size:
            flush()
            if current_pieces and current_length + len(piece) + 1 > chunk_size:
                flush(carry_overlap=False)
 
        current_pieces.append(piece)
        current_length += len(piece) + 1
 
    for paragraph in paragraphs:
        if len(paragraph) <= chunk_size:
            # Small enough to potentially sit as one unbroken piece.
            add_piece(paragraph)
            continue
 
        # Paragraph is too big to add as one piece -- split into sentences.
        for sentence in split_into_sentences(paragraph):
            if len(sentence) > chunk_size:
                # SAFETY NET: even a single sentence is too long (e.g. a
                # bullet-separated line with no punctuation to split on).
                # Flush whatever we have, then hard-split just this piece.
                flush(carry_overlap=False)
                chunks.extend(_hard_split(sentence, chunk_size, overlap=50))
                continue
 
            add_piece(sentence)
 
    flush(carry_overlap=False)  # emit whatever's left, nothing to carry into
 
    return chunks
 
 
def generate_document_id(file_path):
    """
    Create a short, stable ID for a document based on its path.
 
    Why hash the path instead of just using the filename? Two different
    files can share a filename (e.g. "cv.pdf" in two different folders),
    so the filename alone isn't a reliable unique identifier. Hashing the
    full absolute path guarantees a consistent, unique ID -- the same
    file always produces the same ID, and different files (almost)
    never collide.
    """
    absolute_path = str(Path(file_path).resolve())
    return hashlib.md5(absolute_path.encode()).hexdigest()[:12]  # 12 chars is plenty
 
 
def get_document_metadata(file_path, text):
    """
    Build a metadata dictionary describing a document.
 
    This is what lets you trace a chunk back to where it came from later
    -- once chunks are embedded and stored, the original file path is
    the only thing that tells you "this answer came from my_cv.pdf".
    """
    path = Path(file_path)
 
    return {
        "document_id": generate_document_id(file_path),
        "filename": path.name,
        "file_path": str(path.resolve()),
        "file_extension": path.suffix.lower(),
        "file_size_bytes": path.stat().st_size,
        "char_count": len(text),
        "word_count": len(text.split()),
    }
 
 
def chunk_document(file_path, text, chunk_size=200, overlap=1):
    """
    Read a document, chunk it, and attach metadata to every chunk.
 
    Note: `overlap` means "number of sentences repeated between chunks,"
    not characters -- a holdover name from an earlier character-based
    version of this chunker. A large value (e.g. 50) will cause most of
    one chunk to repeat verbatim at the start of the next one, since
    it's asking to carry over 50 whole sentences, not 50 characters.
    1-2 is normally plenty.
 
    Returns a list of dictionaries instead of plain strings, e.g.:
 
        [
          {
            "text": "Mohamed Ewees ... DevOps Lead ...",
            "metadata": {
              "document_id": "a1b2c3d4e5f6",
              "filename": "cv.docx",
              "file_path": "/full/path/to/cv.docx",
              "chunk_index": 0,
              "chunk_id": "a1b2c3d4e5f6_0",
              ...
            }
          },
          ...
        ]
 
    Why chunk_index AND chunk_id? chunk_index (0, 1, 2, ...) tells you
    the chunk's position within its document -- useful for re-assembling
    or showing "chunk 3 of 12". chunk_id combines document_id + index
    into one globally unique string -- useful as a dictionary key or
    database primary key once you're storing chunks from many documents
    together and need every chunk to have its own unique identifier.
    """
    doc_metadata = get_document_metadata(file_path, text)
 
    chunks = chunk_text(text, chunk_size=chunk_size, overlap_sentences=overlap)
 
    chunk_records = []
    for i, chunk in enumerate(chunks):
        chunk_records.append({
            "text": chunk,
            "metadata": {
                **doc_metadata,
                "chunk_index": i,
                "chunk_id": f"{doc_metadata['document_id']}_{i}",
                "chunk_char_count": len(chunk),
            },
        })
 
    return chunk_records
