# `chunker.py`

## Purpose

`chunker.py` takes the plain text produced by `parser.py` and splits it
into overlapping, size-bounded chunks — the units that will eventually
get embedded and searched over. It also generates metadata that traces
every chunk back to the document it came from.

The chunking strategy is **paragraph-aware and sentence-aware**: it
tries hard to keep whole paragraphs together, falls back to splitting by
sentence when a paragraph is too big, and falls back further to raw
character-splitting only as a last resort — with a hard guarantee that
no chunk ever exceeds the requested size, no matter what the input looks
like.

---

## Functions

### `split_into_sentences(paragraph)`

Splits a paragraph into a list of sentences using the regex:

```python
SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
```

In plain terms: split at any point where a `.`, `!`, or `?` is followed
by whitespace and then a capital letter. This is a lightweight
heuristic, not a full NLP sentence tokenizer — it won't correctly
handle abbreviations (`"Dr. Smith"`), and a bullet-point line with no
punctuation at all won't split into multiple sentences (it comes back
as one long "sentence"). That second case is exactly why `_hard_split`
exists — see below.

---

### `_hard_split(text, max_len, overlap=50)`

The safety-net splitter. This is a plain character-based sliding window
— no sentence-awareness at all. It's only called when sentence-aware
splitting has already failed to produce something short enough (i.e. a
single "sentence" is still longer than `chunk_size` on its own — common
with bullet-separated skill lists or long unpunctuated lines).

**How it works:** slide a window of `max_len` characters across the
text, stripping each slice and adding it to the result list. Step the
window forward by `max_len - overlap` each time (i.e. move forward by
`max_len` but back up by `overlap`), so consecutive pieces share some
characters at the boundary for context continuity.

This is the piece that guarantees `chunk_size` is a genuine hard
ceiling — without it, a paragraph with no punctuation could produce a
chunk of unbounded size.

---

### `chunk_text(text, chunk_size=500, overlap_sentences=1)`

The core chunking function. Returns a list of plain strings.

**Parameters:**
- `chunk_size` (`int`) — maximum characters per chunk. This is a hard
  ceiling; no returned chunk will ever exceed it.
- `overlap_sentences` (`int`) — how many pieces (sentences, or whole
  short paragraphs) get repeated at the start of the next chunk, so
  context survives a chunk boundary.

**Raises:** `ValueError` if `chunk_size <= 0` or `overlap_sentences <
0`.

**Algorithm, step by step:**

1. **Split into paragraphs** on blank lines (`re.split(r"\n\s*\n",
   text)`).
2. **For each paragraph:**
   - If the whole paragraph fits within `chunk_size`, try to add it as
     one unbroken piece (via `add_piece`, below).
   - If it's too big, split it into sentences and add each sentence as
     its own piece — *unless* a single sentence is itself bigger than
     `chunk_size`, in which case it gets force-split via `_hard_split`
     instead.
3. **`add_piece(piece)`** decides, for every piece added, whether it
   fits in the chunk currently being built. If not, it flushes the
   current chunk out and starts a new one, carrying the overlap
   forward.
4. At the very end, whatever's left in progress gets flushed as the
   final chunk.

**Two internal helper closures do the bookkeeping:**

#### `flush(carry_overlap=True)`

Emits the chunk being built (joins its pieces with `" "` and appends the
result to `chunks`), then either:
- carries the last `overlap_sentences` pieces forward into the next
  chunk (if `carry_overlap=True`), or
- clears everything and starts the next chunk from scratch (if
  `carry_overlap=False` — used after a hard-split, or at the very end,
  where there's nothing meaningful left to carry into).

#### `add_piece(piece)`

Adds a single piece (a paragraph or a sentence) to the chunk currently
being assembled, flushing first if needed. This function checks whether
the piece fits **twice**:

```python
if current_pieces and current_length + len(piece) + 1 > chunk_size:
    flush()
    if current_pieces and current_length + len(piece) + 1 > chunk_size:
        flush(carry_overlap=False)

current_pieces.append(piece)
current_length += len(piece) + 1
```

**Why check twice?** After a normal `flush()`, the carried-over overlap
becomes the start of the new chunk. If that carried-over overlap is
already close to `chunk_size` on its own, adding the next piece on top
of it could *still* overflow the limit — a single check isn't enough to
guarantee the ceiling holds. The second check catches exactly that case:
if the piece still doesn't fit even after the overlap carry, the
overlap is dropped for that one boundary (`flush(carry_overlap=False)`)
rather than letting the chunk grow past `chunk_size`.

**Known minor edge case:** in rare situations where `chunk_size` is
small relative to typical sentence length, this can produce a tiny
duplicate chunk (the lone overlap sentence flushed out on its own,
identical to the tail of the previous chunk) rather than merging
smoothly. This doesn't break the size guarantee — it's a cosmetic
inefficiency, not a correctness issue.

```python
from chunker import chunk_text

chunks = chunk_text(document_text, chunk_size=500, overlap_sentences=1)
# chunks is a list of strings, e.g. ["Paragraph one...", "Paragraph two...", ...]
```

---

### `generate_document_id(file_path)`

Builds a short, stable identifier for a document by MD5-hashing its
**absolute** path and truncating to 12 hex characters.

**Why hash the absolute path instead of just using the filename?** Two
different files can share a filename (`cv.pdf` in two different
folders) — the filename alone isn't a reliable unique key. Hashing the
resolved absolute path means the same file always produces the same ID,
and different files essentially never collide.

---

### `get_document_metadata(file_path, text)`

Builds a metadata dictionary describing a document as a whole (not a
specific chunk):

```python
{
    "document_id": "a1b2c3d4e5f6",
    "filename": "cv.docx",
    "file_path": "/full/resolved/path/to/cv.docx",
    "file_extension": ".docx",
    "file_size_bytes": 17800,
    "char_count": 4933,
    "word_count": 629,
}
```

This is the information that eventually lets you trace a search result
back to "this came from `cv.docx`" once chunks are embedded and stored
in a vector database — the original file path is the only thing
connecting a chunk of text back to its source once it's sitting in a
database alongside thousands of other chunks.

---

### `chunk_document(file_path, text, chunk_size=200, overlap=1)`

The all-in-one function you'll actually call day to day: builds
document metadata, chunks the text, and attaches metadata to every
individual chunk.

**Parameters:**
- `file_path` — used to generate the document ID and locate metadata
  like file size.
- `text` — the already-extracted document text (from
  `parser.read_document()`).
- `chunk_size` — forwarded directly to `chunk_text()`.
- `overlap` — forwarded to `chunk_text()`'s `overlap_sentences`
  parameter. **Important naming note:** despite the parameter being
  called `overlap`, it means "how many sentences to repeat," not "how
  many characters." This is a holdover name from an earlier
  character-based version of the chunker. Passing something like `50`
  (a sensible value for the old character-based system) will instead
  ask to carry over *50 whole sentences* between chunks, which for most
  text means most of one chunk repeating verbatim at the start of the
  next. Keep this small — `1` or `2` is normally plenty.

**Returns:** a list of dictionaries, one per chunk:

```python
[
    {
        "text": "AWS Certified Solutions Architect and DevOps Lead...",
        "metadata": {
            "document_id": "a1b2c3d4e5f6",
            "filename": "cv.docx",
            "file_path": "/full/path/to/cv.docx",
            "file_extension": ".docx",
            "file_size_bytes": 17800,
            "char_count": 4933,
            "word_count": 629,
            "chunk_index": 0,
            "chunk_id": "a1b2c3d4e5f6_0",
            "chunk_char_count": 424,
        },
    },
    ...
]
```

**Why both `chunk_index` and `chunk_id`?**
- `chunk_index` (`0`, `1`, `2`, ...) is the chunk's position within its
  own document — useful for showing "chunk 3 of 12" or re-assembling
  a document from its chunks in order.
- `chunk_id` combines `document_id` and `chunk_index` into one string
  that's unique across *every* document, not just within one — useful
  once you're storing chunks from many different documents together
  (e.g. as a dictionary key or a database primary key) and need every
  single chunk to have its own unambiguous identifier.

```python
from parser import read_document
from chunker import chunk_document

text = read_document("cv.docx")
records = chunk_document("cv.docx", text, chunk_size=200, overlap=1)

for record in records:
    print(record["metadata"]["chunk_id"], "->", record["text"][:50])
```

---

## Design notes / things to know if you extend this

- **`chunk_text()` and `chunk_document()` are separate on purpose.**
  `chunk_text()` is the pure text-splitting logic with no file-system or
  metadata concerns — reusable on any string, not just something read
  from disk. `chunk_document()` is the convenience wrapper that adds
  file-awareness on top. If you ever need to chunk text that didn't
  come from a file (e.g. text pasted directly, or scraped from a web
  page), `chunk_text()` still works standalone.
- **The `overlap` naming inconsistency between `chunk_document` and
  `chunk_text`** (`overlap` vs. `overlap_sentences`) is a known rough
  edge — worth renaming for consistency if this code keeps evolving,
  just be sure to update every call site if you do.
- **`chunk_size` is measured in characters, not tokens.** If you later
  plug chunks into an embedding model with a token limit (rather than a
  character limit), you'll want to convert — roughly 4 characters per
  token is a common rule of thumb for English text, but it's an
  approximation, not exact.
