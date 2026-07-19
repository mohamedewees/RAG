# `main.py`

## Purpose

`main.py` is the entry-point script that ties `parser.py` and
`chunker.py` together into a runnable end-to-end demo: read a document,
chunk it two different ways, and print the results. It's meant for
manual inspection while developing — not (yet) a reusable function other
code would import.

---

## What it does, step by step

```python
from parser import read_document
from chunker import chunk_document, chunk_text

if __name__ == "__main__":
    file_path = r"/path/to/Mohammed_Ewees.docx"

    text = read_document(file_path)
    chunks = chunk_text(text, chunk_size=200, overlap_sentences=1)
```

1. **Read the document.** `read_document()` (from `parser.py`) picks the
   right reader based on the file extension and returns cleaned plain
   text.

2. **Chunk it with `chunk_text()`.** This is the plain version — returns
   a list of strings with no metadata attached. Called here with
   `chunk_size=200` and `overlap_sentences=1`.

```python
    print(f"Loaded and chunked {file_path} into {len(chunks)} chunks:\n")
    for i, chunk in enumerate(chunks):
        print(f"--- Chunk {i} ({len(chunk)} chars) ---")
        print(chunk)
        print()
```

3. **Print every chunk** with its index and character count, so you can
   visually confirm nothing's being cut mid-sentence or exceeding the
   size limit.

```python
    chunk_records = chunk_document(file_path, text, chunk_size=200, overlap=1)
    for record in chunk_records:
        print(f"--- {record['metadata']['chunk_id']} ---")
        print(f"From: {record['metadata']['filename']}")
        print(record["text"][:80] + "...")
        print()
```

4. **Chunk it again with `chunk_document()`** — the metadata-aware
   version — using the *same* `chunk_size` as step 2, so the two outputs
   are a fair comparison rather than showing differently-sized chunks.
   This prints each chunk's `chunk_id`, source filename, and a preview
   of its text, demonstrating what the metadata adds on top of the plain
   chunking in step 2.

---

## Why call `chunk_text()` and `chunk_document()` separately here,
## when `chunk_document()` already calls `chunk_text()` internally?

Purely for demonstration. Running both side by side (with matching
`chunk_size`) shows you exactly what `chunk_document()` adds on top of
`chunk_text()` — the metadata dictionary wrapped around each identical
chunk of text. In real usage you'd normally only call `chunk_document()`
directly rather than running the text-splitting twice.

---

## Known limitations of this script as it stands

- **The file path is hardcoded** at the top of the script
  (`r"/home/mohamed-ewees/Downloads/..."`). Running this on a different
  machine means editing the script directly, since there's no
  command-line argument or configuration file. A natural next
  improvement: accept the path as a command-line argument (e.g. via
  `sys.argv[1]` or the `argparse` module) instead.
- **No error handling.** If the file doesn't exist, or is a format
  `read_document()` doesn't support, the script will crash with an
  unhandled exception and a raw traceback rather than a clean error
  message.
- **This is a script, not a library.** Nothing here is wrapped in a
  function other code could import and call — it's meant to be run
  directly (`python main.py`) as a manual test/demo, not imported
  elsewhere. If this pipeline grows (adding `embedder.py`,
  `vectordb.py`, etc.), `main.py` will likely evolve into the
  orchestration point that wires all the stages together — at that
  point it's worth revisiting whether the hardcoded path and lack of
  error handling still make sense.

```bash
python main.py
```

No arguments — just run it directly, after updating the `file_path`
variable to point at whatever document you want to test.
