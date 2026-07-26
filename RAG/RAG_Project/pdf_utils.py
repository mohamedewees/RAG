"""
pdf_utils.py

PDF-specific cleanup logic that goes beyond plain text extraction:

  1. Detecting and stripping repeating page headers/footers (breadcrumbs,
     export timestamps, "Page N" markers) that pypdf extracts as if they
     were body content.
  2. Detecting and skipping table-of-contents pages, which contribute
     dot-leader noise and duplicate heading text with no retrieval value.
  3. Extracting embedded images (diagrams, screenshots) and generating a
     text description of each via Claude's vision capability, so content
     that only exists as pixels becomes searchable text.

This is kept separate from parser.py because it's a different KIND of
problem than "read this file format" -- it's pattern-detection heuristics
plus an external API call, not a straightforward format reader.
"""

import re
import base64
from collections import Counter


# --------------------------------------------------------------------------
# 1. Header / footer detection
# --------------------------------------------------------------------------

def strip_boilerplate_lines(page_texts, min_repeat_ratio=0.5):
    """
    Detects and removes lines that repeat across most pages -- the
    signature of a running header or footer, as opposed to actual
    content.

    How it works: for each page, look only at the first two and last two
    lines (headers/footers live at the page edges, not buried in the
    middle of content). Count how many DIFFERENT pages each such line
    appears on. Any line appearing on at least `min_repeat_ratio` of all
    pages gets treated as boilerplate and stripped from every page.

    Why only look at edge lines? A real sentence could coincidentally
    repeat (e.g. a warning box on multiple pages) -- restricting the
    search to page edges makes false positives much less likely, since
    genuine repeated body content rarely sits at the very top/bottom of
    every page.

    Also strips lines matching "Page <number>" specifically, since page
    numbers change per page and won't be caught by exact-match repetition.
    """
    page_lines = [pt.splitlines() for pt in page_texts]
    total_pages = len(page_lines)

    if total_pages < 3:
        # Not enough pages to reliably distinguish "repeats because it's
        # boilerplate" from "repeats by coincidence" -- skip detection.
        return page_texts

    line_page_counts = Counter()
    for lines in page_lines:
        edge_lines = lines[:2] + lines[-2:]
        for line in {l.strip() for l in edge_lines if l.strip()}:
            line_page_counts[line] += 1

    boilerplate = {
        line for line, count in line_page_counts.items()
        if count / total_pages >= min_repeat_ratio
    }

    page_number_pattern = re.compile(r"^Page\s+\d+$", re.IGNORECASE)

    cleaned_pages = []
    for lines in page_lines:
        kept = [
            line for line in lines
            if line.strip() not in boilerplate
            and not page_number_pattern.match(line.strip())
        ]
        cleaned_pages.append("\n".join(kept))

    return cleaned_pages


# --------------------------------------------------------------------------
# 2. Table-of-contents detection
# --------------------------------------------------------------------------

def is_toc_page(page_text):
    """
    Heuristically detects whether a page is a table of contents.

    Two signals, either one is enough:
      1. A line that's just "Table of Contents" (the overwhelmingly
         common literal heading for this in exported documents).
      2. Several lines ending in a dot-leader pattern (". . . . 4") --
         the visual connector between a heading and its page number.
         A handful of these on one page is a strong TOC signature that
         essentially never occurs in ordinary prose.
    """
    if re.search(r"^\s*table of contents\s*$", page_text, re.IGNORECASE | re.MULTILINE):
        return True

    dot_leader_lines = len(re.findall(r"[.\s]{10,}\d+\s*$", page_text, re.MULTILINE))
    return dot_leader_lines >= 3


# --------------------------------------------------------------------------
# 3. Image extraction + description
# --------------------------------------------------------------------------

# def extract_images(reader, min_width=80, min_height=80):
#     """
#     Extracts embedded images from every page of a pypdf PdfReader,
#     skipping small images (icons, bullet graphics, logos) that aren't
#     worth describing.

#     Returns a list of dicts: {page_index, name, data, width, height}
#     """
#     images = []

#     for page_index, page in enumerate(reader.pages):
#         for image_file in page.images:
#             try:
#                 pil_image = image_file.image
#                 width, height = pil_image.size
#             except Exception:
#                 width, height = None, None

#             if width and height and (width < min_width or height < min_height):
#                 continue  # too small to be a meaningful diagram/screenshot

#             images.append({
#                 "page_index": page_index,
#                 "name": image_file.name,
#                 "data": image_file.data,
#                 "width": width,
#                 "height": height,
#             })

#     return images


#######DeepSeek modifications###############

# pdf_utils.py

def extract_images(reader, min_width=80, min_height=80):
    """
    Extracts embedded images from every page of a pypdf PdfReader.
    Enhanced to catch images that page.images might miss.
    """
    images = []
    
    for page_index, page in enumerate(reader.pages):
        print(f"Checking page {page_index} for images...")
        
        # Method 1: Standard page.images (most common)
        try:
            for image_file in page.images:
                try:
                    pil_image = image_file.image
                    width, height = pil_image.size
                    print(f"  Found image via page.images: {image_file.name} ({width}x{height})")
                except Exception as e:
                    width, height = None, None
                    print(f"  Found image via page.images: {image_file.name} (size error: {e})")
                
                if width and height and (width < min_width or height < min_height):
                    print(f"    Skipping - too small ({width}x{height})")
                    continue
                
                images.append({
                    "page_index": page_index,
                    "name": image_file.name,
                    "data": image_file.data,
                    "width": width,
                    "height": height,
                })
                print(f"    Kept image: {image_file.name}")
        except Exception as e:
            print(f"  page.images extraction failed: {e}")
        
        # Method 2: Look for images in XObjects (catches Confluence exports)
        try:
            if '/XObject' in page['/Resources']:
                xobjects = page['/Resources']['/XObject'].get_object()
                for obj_name in xobjects:
                    obj = xobjects[obj_name]
                    if obj.get('/Subtype') == '/Image':
                        width = obj.get('/Width', 0)
                        height = obj.get('/Height', 0)
                        print(f"  Found XObject image: {obj_name} ({width}x{height})")
                        
                        if width < min_width or height < min_height:
                            print(f"    Skipping - too small ({width}x{height})")
                            continue
                        
                        # Extract the image data
                        try:
                            # Try to get the image data
                            if hasattr(obj, 'get_data'):
                                image_bytes = obj.get_data()
                            else:
                                # Alternative extraction method
                                from pypdf.generic import IndirectObject
                                if isinstance(obj, IndirectObject):
                                    obj = obj.get_object()
                                if hasattr(obj, 'get_object'):
                                    obj = obj.get_object()
                                
                                # For some PDFs, the data is in '/Raw'
                                if '/Raw' in obj:
                                    image_bytes = obj['/Raw'].get_object()
                                else:
                                    # For standard images, we need to get the data
                                    from pypdf.filters import FlateDecode, DCTDecode, JPXDecode
                                    import io
                                    
                                    data = obj.get_data() if hasattr(obj, 'get_data') else b''
                                    if data:
                                        image_bytes = data
                                    else:
                                        # Try to get from the underlying stream
                                        if hasattr(obj, '_data'):
                                            image_bytes = obj._data
                                        else:
                                            continue
                            
                            # Determine image type from name or filter
                            img_name = f"XObject_{obj_name}"
                            
                            images.append({
                                "page_index": page_index,
                                "name": img_name,
                                "data": image_bytes,
                                "width": width,
                                "height": height,
                            })
                            print(f"    Kept XObject image: {obj_name}")
                        except Exception as e:
                            print(f"    Could not extract XObject image data: {e}")
        except Exception as e:
            print(f"  XObject extraction failed: {e}")
    
    print(f"Total images found: {len(images)}")
    return images

############################################

def describe_image_with_claude(image_bytes, media_type="image/png", model="claude-sonnet-5"):
    """
    Sends an image to Claude's API and returns a text description of it.

    Requires internet access, `pip install anthropic`, and an
    ANTHROPIC_API_KEY environment variable. NOT suitable for an
    air-gapped / fully offline deployment -- see describe_image_offline()
    and extract_text_from_image_ocr() below for local alternatives.
    """
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "describe_image_with_claude() requires the 'anthropic' package. "
            "Install it with: pip install anthropic"
        )

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment

    b64_data = base64.standard_b64encode(image_bytes).decode("utf-8")

    message = client.messages.create(
        model=model,
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": b64_data},
                },
                {"type": "text", "text": IMAGE_DESCRIPTION_PROMPT},
            ],
        }],
    )

    return message.content[0].text


def describe_image_offline(image_bytes, model="llava", ollama_host="http://localhost:11434"):
    """
    Sends an image to a LOCALLY RUNNING vision model via Ollama and
    returns a text description -- a fully offline drop-in replacement
    for describe_image_with_claude().

    One-time setup (needs internet ONCE, to download the model):
        1. Install Ollama: https://ollama.com/download
        2. Pull a vision-capable model, e.g.:
             ollama pull llava        # general purpose, ~4.7GB, good default
             ollama pull qwen2.5vl    # notably better at reading small
                                      # text/labels inside diagrams --
                                      # worth it if your documents have
                                      # a lot of technical diagrams
             ollama pull moondream    # ~1.6GB, much lighter weight, use
                                      # if GPU/RAM is constrained
        3. Make sure the Ollama service is running (`ollama serve`, or
           it may already run as a background service after install).

    After that setup, every call here is a request to localhost --
    ZERO calls leave the machine. This is the right choice for an
    air-gapped deployment.

    Raises RuntimeError with setup instructions if Ollama isn't reachable,
    rather than a raw connection-refused traceback.
    """
    try:
        import requests
    except ImportError:
        raise RuntimeError(
            "describe_image_offline() requires the 'requests' package. "
            "Install it with: pip install requests"
        )

    b64_data = base64.standard_b64encode(image_bytes).decode("utf-8")

    try:
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={
                "model": model,
                "prompt": IMAGE_DESCRIPTION_PROMPT,
                "images": [b64_data],
                "stream": False,
            },
            timeout=120,
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"Could not reach Ollama at {ollama_host}. Is it installed and running? "
            f"See describe_image_offline()'s docstring for setup steps."
        )

    return response.json()["response"].strip()


# def extract_text_from_image_ocr(image_bytes):
#     """
#     Lightweight, fully offline fallback: runs OCR (Tesseract) on the
#     image and returns whatever text it can read, WITHOUT any AI model.

#     Trade-off vs. the two functions above: this only recovers text that
#     is literally printed in the image (box labels, titles) -- it cannot
#     describe relationships between components (which arrow connects to
#     which box, what a failover path means) the way a real vision model
#     can. But it needs no GPU, no model download, and no external
#     service -- just `pip install pytesseract` plus the `tesseract-ocr`
#     system package. Good option when hardware is constrained or when
#     "some searchable text is better than none" is good enough.
#     """
#     try:
#         import pytesseract
#         from PIL import Image
#         import io
#     except ImportError:
#         raise RuntimeError(
#             "extract_text_from_image_ocr() requires 'pytesseract' and 'Pillow'. "
#             "Install with: pip install pytesseract pillow "
#             "(and the tesseract-ocr system package, e.g. apt-get install tesseract-ocr)"
#         )

#     image = Image.open(io.BytesIO(image_bytes))
#     text = pytesseract.image_to_string(image).strip()

#     if not text:
#         return "[Diagram/image present; no machine-readable text detected in it.]"

#     # Collapse the raggedness OCR output tends to have (odd line breaks,
#     # repeated blank lines) into something more chunking-friendly.
#     cleaned_lines = [line.strip() for line in text.splitlines() if line.strip()]
#     return "Diagram/image containing the following visible text: " + "; ".join(cleaned_lines)


# IMAGE_DESCRIPTION_PROMPT = (
#     "Describe this diagram factually for someone who cannot see it. "
#     "Focus on: what components/services are shown, how they connect "
#     "or relate to each other, and any labels or text visible in the "
#     "image. Be concise -- 3 to 5 sentences. Do not speculate beyond "
#     "what's actually visible."
# )

###########DeepSeek Modification#################

# Enhanced OCR with preprocessing
def extract_text_from_image_ocr(image_bytes):
    """Better OCR with image preprocessing."""
    try:
        import pytesseract
        from PIL import Image, ImageEnhance, ImageFilter
        import io
        
        # Load image
        img = Image.open(io.BytesIO(image_bytes))
        
        # Preprocess for better OCR
        # Convert to grayscale
        if img.mode != 'L':
            img = img.convert('L')
        
        # Enhance contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        
        # Sharpen
        img = img.filter(ImageFilter.SHARPEN)
        
        # OCR with better configuration
        text = pytesseract.image_to_string(
            img, 
            config='--psm 6 --oem 3'  # Page segmentation mode 6, LSTM OCR
        )
        
        return text.strip() if text.strip() else "[No text found in image]"
    except Exception as e:
        return f"[OCR failed: {e}]"

#################################################


def describe_image(image_bytes, media_type="image/png", backend="ocr", **kwargs):
    """
    Single entry point for image description, dispatching to whichever
    backend you choose:

        backend="ocr"     -- fully offline, no model, text-only (default)
        backend="offline" -- fully offline, needs local Ollama + a vision model
        backend="claude"  -- needs internet + an API key, highest quality

    This is the function parser.py actually calls -- pick your backend
    once here rather than changing call sites all over the codebase.
    """
    if backend == "ocr":
        return extract_text_from_image_ocr(image_bytes)
    elif backend == "offline":
        return describe_image_offline(image_bytes, **kwargs)
    elif backend == "claude":
        return describe_image_with_claude(image_bytes, media_type, **kwargs)
    else:
        raise ValueError(f"Unknown backend '{backend}'. Use 'ocr', 'offline', or 'claude'.")


def guess_media_type(image_name):
    """Maps a pypdf image filename's extension to a media type string."""
    lower = image_name.lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    if lower.endswith(".gif"):
        return "image/gif"
    if lower.endswith(".webp"):
        return "image/webp"
    return "image/png"  # reasonable default; PNG is the most common embedded format