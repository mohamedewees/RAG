import os
import re
from pypdf import PdfReader
import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

def read_text_file(file_path):
    with open(file_path, 'r',encoding='utf-8') as f:
        text = f.read()
    return text

def read_pdf_file(file_path):
    reader = PdfReader(file_path)
    all_text = []
    for page in reader.pages:
        page_text = page.extract_text()
        all_text.append(page_text)
    return "".join(all_text)
    # return all_text

def read_dox(file_path):
    doc = docx.Document(file_path)
    parts = []
    # Header extraction
    for section in doc.sections:
        header_text = "\n".join(p.text for p in section.header.paragraphs if p.text.strip())
        if header_text:
            parts.append(header_text)
    # Main body extraction
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            paragraph = Paragraph(child,doc)
            if paragraph.text.strip():
                parts.append(paragraph.text)
        elif child.tag == qn("w:tbl"):
            table = Table(child,doc)
            for row in table.rows:
                cells_text = [cell.text.strip() for cell in row.cells]
                row_text = "|".join(t for t in cells_text if t)
                if row_text:
                    parts.append(row_text)
    
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
    # clean up messy whitespace so chunking works on tidy text
    text = re.sub(r"[ \t]+"," ", text)   # Collapse repeated spaces/tabs
    text = re.sub(r"\n{3,}","\n\n", text)  # collapse 3+ blank lines to 1
    return text.strip()