import os
import re
from pypdf import PdfReader
import docx
from docx.oxml.ns import qn
 
def read_text_file(file_path):
    with open(file_path, 'r',encoding='utf-8') as f:
        text = f.read()
    return text
 
def read_pdf_file(file_path):
    reader = PdfReader(file_path)
    all_text = []
    for page in reader.pages:
        # extract_text() returns None (not "") for pages with no text
        # layer -- a blank page, a scanned/image-only page, etc.
        # Without "or ''" here, "".join() below crashes on the first
        # such page with: TypeError: sequence item: expected str, NoneType found
        page_text = page.extract_text() or ""
        all_text.append(page_text)
    # joined with "\n\n" (not "") so the last word of one page and the
    # first word of the next don't get glued together with no space
    return "\n\n".join(all_text)
 
def read_dox(file_path):
    """
    Reads headers, main body (paragraphs, tables, AND text boxes no
    matter how deeply nested), and footers.
 
    Why iter(qn("w:p")) instead of iterchildren()? iterchildren() only
    sees direct children of the body -- text inside a table cell or a
    text box lives nested several layers deep and gets silently missed.
    iter() searches the entire tree, so table cells and text boxes are
    caught the same way as ordinary paragraphs. The one thing to guard
    against: a paragraph that WRAPS a text box will itself contain
    another nested <w:p> -- if we counted both, the text would be
    duplicated, so wrapper paragraphs (any <w:p> containing a nested
    <w:p>) are skipped and only the innermost one is kept.
    """
    doc = docx.Document(file_path)
    parts = []
    # Header extraction
    for section in doc.sections:
        header_text = "\n".join(p.text for p in section.header.paragraphs if p.text.strip())
        if header_text:
            parts.append(header_text)
 
    # Main body extraction -- every paragraph anywhere in the tree,
    # in document order, regardless of nesting depth
    for p_elem in doc.element.body.iter(qn("w:p")):
        has_nested_paragraph = any(
            descendant is not p_elem for descendant in p_elem.iter(qn("w:p"))
        )
        if has_nested_paragraph:
            continue  # wrapper paragraph -- the real content is nested inside it
 
        run_texts = [t.text for t in p_elem.iter(qn("w:t")) if t.text]
        paragraph_text = "".join(run_texts).strip()
        if paragraph_text:
            parts.append(paragraph_text)
 
    # Footer extraction
    for section in doc.sections:
        footer_text = "\n".join(p.text for p in section.footer.paragraphs if p.text.strip())
        if footer_text:
            parts.append(footer_text)
    return "\n\n".join(parts)
 
def read_document(file_path):
    extension = os.path.splitext(file_path)[1].lower()
    if extension == ".txt":
        text = read_text_file(file_path)
    elif extension == ".pdf":
        text = read_pdf_file(file_path)
    elif extension == ".docx":
        text = read_dox(file_path)
    else:
        raise ValueError(f"Unsupported file type: {extension}")
    
    if extension == ".md":
        # Markdown is whitespace-sensitive: code blocks and nested lists
        # rely on exact indentation to mean what they mean. Collapsing
        # repeated spaces (the way we do for prose below) would flatten
        # a 4-space-indented code block and turn nested bullets into
        # siblings -- silently corrupting the document's structure. So
        # for markdown we skip that step and only trim outer whitespace.
        return text.strip()

    # clean up messy whitespace so chunking works on tidy text
    text = re.sub(r"[ \t]+"," ", text)   # Collapse repeated spaces/tabs
    text = re.sub(r"\n{3,}","\n\n", text)  # collapse 3+ blank lines to 1
    return text.strip()