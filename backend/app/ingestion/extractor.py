"""
Document Ingestion & Text Extraction Pipeline.
Extracts content, page numbers, sections, and metadata from PDF, DOCX, TXT, and C/C++ files.
Treats all document text as untrusted data.
"""
import os
import re
from typing import List, Dict, Any

def extract_text_from_pdf(file_path: str) -> List[Dict[str, Any]]:
    """
    Extracts text per page from a PDF file using pypdf and OCR for image-only pages.
    Returns list of dicts: [{"page": 1, "text": "...", "headings": [...]}]
    """
    pages_data = []
    try:
        from pypdf import PdfReader
    except Exception as e:
        raise RuntimeError(f"PDF parsing requires pypdf: {e}") from e

    reader = PdfReader(file_path)
    ocr_document = None
    for page_idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if not text.strip():
            try:
                import pypdfium2
                import pytesseract
            except ImportError as e:
                raise RuntimeError(
                    "This PDF contains scanned pages. Install pypdfium2 and pytesseract, "
                    "and install the Tesseract OCR application to extract them."
                ) from e
            try:
                if ocr_document is None:
                    ocr_document = pypdfium2.PdfDocument(file_path)
                image = ocr_document[page_idx - 1].render(scale=2).to_pil()
                text = pytesseract.image_to_string(image) or ""
            except Exception as e:
                raise RuntimeError(
                    f"OCR failed on scanned PDF page {page_idx}; verify the Tesseract installation: {e}"
                ) from e

        headings = [
            line.strip() for line in text.splitlines()
            if line.strip().isupper() and len(line.strip()) < 80
        ]
        pages_data.append({"page": page_idx, "text": text, "headings": headings})
    return pages_data

def extract_text_from_docx(file_path: str) -> List[Dict[str, Any]]:
    """
    Extracts text from a DOCX file using python-docx.
    """
    pages_data = []
    try:
        import docx
        doc = docx.Document(file_path)
        full_text = []
        headings = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                if para.style.name.startswith("Heading"):
                    headings.append(text)
                full_text.append(text)
        
        # Also extract table text
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    full_text.append(row_text)

        pages_data.append({
            "page": 1,
            "text": "\n\n".join(full_text),
            "headings": headings
        })
    except Exception as e:
        pages_data.append({
            "page": 1,
            "text": f"Error parsing DOCX: {str(e)}",
            "headings": []
        })
    return pages_data

def extract_text_from_code_or_text(file_path: str) -> List[Dict[str, Any]]:
    """
    Extracts text from plain text or source code files (.c, .h, .cpp, .txt, .json).
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        content = f"Error reading file: {str(e)}"

    # Detect functions in C/C++
    function_names = re.findall(r"(?:void|int|uint\d+_t|Std_ReturnType|bool|float)\s+([A-Za-z0-9_]+)\s*\(", content)

    return [{
        "page": 1,
        "text": content,
        "headings": function_names
    }]

def extract_document(file_path: str, file_type: str) -> List[Dict[str, Any]]:
    ext = file_type.lower().replace(".", "")
    if ext == "pdf":
        return extract_text_from_pdf(file_path)
    elif ext in ["docx", "doc"]:
        return extract_text_from_docx(file_path)
    else:
        return extract_text_from_code_or_text(file_path)
