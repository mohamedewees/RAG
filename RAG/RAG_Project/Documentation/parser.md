# `parser.py`

## Purpose

`parser.py` is the document-reading stage of the RAG pipeline. It takes a
file on disk — `.txt`, `.pdf`, or `.docx` — and returns its contents as a
single, cleaned-up plain-text string. Everything downstream (chunking,
embedding, retrieval) works on plain text, so this module's job is to
hide the format-specific mess and hand back something uniform.

It has one public entry point, `read_document()`, and three private
readers behind it — one per file type.

---

## Functions

### `read_document(file_path)`

The main entry point. Call this one; the others are implementation
details it dispatches to.

**What it does:**
1. Looks at the file extension (`os.path.splitext`) to decide which
   reader to use.
2. Calls the matching reader (`read_text_file`, `read_pdf_file`, or
   `read_dox`) to get the raw extracted text.
3. Normalizes whitespace: collapses repeated spaces/tabs into one, and
   collapses 3+ blank lines down to a single blank line.
4. Strips leading/trailing whitespace and returns the final string.

**Parameters:**
- `file_path` (`str`) — path to the document.

**Returns:** `str` — the cleaned plain text of the document.

**Raises:** `ValueError` if the extension isn't `.txt`, `.pdf`, or
`.docx`.

**Why normalize whitespace here, centrally, instead of in each reader?**
Different formats produce messy whitespace in different ways (PDFs
especially), and centralizing the cleanup means every format gets the
same treatment and the chunker downstream never has to think about it.

```python
from parser import read_document

text = read_document("my_cv.docx")
```

---

### `read_text_file(file_path)`

Reads a `.txt` file and returns its raw contents. The simplest of the
three readers — just opens the file with UTF-8 encoding and reads it.

---

### `read_pdf_file(file_path)`

Reads a `.pdf` file page by page using `pypdf.PdfReader`, and joins the
extracted text from every page together.

**Two details worth knowing:**

1. **`page.extract_text() or ""`** — `pypdf` returns `None` (not an
   empty string) for a page with no text layer, such as a blank page or
   a scanned/image-only page. Without the `or ""` fallback, joining a
   list containing `None` raises `TypeError: sequence item: expected
   str instance, NoneType found` the moment such a page is encountered.
   This guard means a PDF with a blank or scanned page won't crash the
   whole pipeline — that page just contributes no text.

2. **Pages are joined with `"\n\n"`, not `""`.** If page boundaries
   aren't separated, the last word on one page and the first word on
   the next can run together with no space at all (e.g.
   `"...conclusion.Chapter 2..."`), corrupting both words for any
   downstream sentence-splitting or embedding.

**Limitation to know about:** this only extracts text that's actually
present in the PDF's text layer. A scanned document with no text layer
(pure images) will extract as empty text for every page — that
requires OCR, which this function doesn't do.

---

### `read_dox(file_path)`

Reads a `.docx` file, capturing text from **headers, the main body
(including tables and text boxes, no matter how deeply nested), and
footers.**

This is the most involved reader, because a Word document isn't a flat
stream of text — headers/footers live in an entirely separate part of
the file, and the body itself is a tree where a name or heading can be
buried inside a table cell or a text box several layers deep.

**How it works, in three passes:**

1. **Headers** — loop through `doc.sections` and pull
   `section.header.paragraphs`. Headers are stored completely separately
   from the main body, so nothing else in this function would ever see
   them without this explicit pass.

2. **Main body** — instead of `doc.paragraphs` (which only sees
   top-level paragraphs and misses anything nested) or
   `doc.element.body.iterchildren()` (which only sees *direct* children
   and misses anything nested one level deeper, like a table cell or
   text box), this walks the **entire XML tree** with
   `doc.element.body.iter(qn("w:p"))`. That finds every `<w:p>`
   (paragraph) element anywhere in the document, regardless of how
   deeply it's nested — table cells, text boxes, all of it.

   **The wrapper-paragraph guard:** a text box is structurally a
   paragraph *nested inside* another paragraph's drawing object. If both
   the outer wrapper and the inner nested paragraph were counted, the
   text box's content would be captured twice. So for each paragraph
   found, the code checks whether it contains another `<w:p>` nested
   inside itself:

   ```python
   has_nested_paragraph = any(
       descendant is not p_elem for descendant in p_elem.iter(qn("w:p"))
   )
   if has_nested_paragraph:
       continue  # this is just a wrapper; the real content is nested inside it
   ```

   Only "leaf" paragraphs (ones with no further paragraph nested inside
   them) get their text extracted, which naturally covers ordinary
   paragraphs, table cell paragraphs, and text-box paragraphs alike,
   without double-counting.

3. **Footers** — same reasoning and same approach as headers.

**Returns:** all captured text joined with `"\n\n"`, in the order:
headers → body content (in document order) → footers.

---

## Design notes / things to know if you extend this

- **No PowerPoint or HTML support yet.** Adding a new format means
  writing a new `_read_xxx` function and adding a branch to
  `read_document`'s dispatch logic.
- **This module has no concept of metadata** (document ID, file size,
  etc.) — that's deliberately kept in `chunker.py`'s
  `get_document_metadata()`, since metadata generation only needs the
  file path and the already-extracted text, not any format-specific
  logic.
- **OCR is out of scope.** If you need to handle scanned PDFs or images
  with embedded text, that's a different tool (e.g. `pytesseract`) and
  a different code path, not something `read_pdf_file` currently does.
