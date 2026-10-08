"""
Document Chunker.
Splits extracted document pages into contextual chunks with metadata.
"""
from typing import List, Dict, Any

import re

def _detect_chunk_section(text: str, default_section: str) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines[:3]:
        if set(line) in [{'-'}, {'='}, {'*'}]:
            continue
        m = re.match(r'^(\d+(\.\d+)*\.?\s+[^:\n]+)', line)
        if m:
            return m.group(1).strip()
        if re.match(r'^[A-Z0-9_\s]{3,60}$', line) and not line.startswith('HTTP') and not line.startswith('NOTE'):
            return line.strip()
    return default_section

def chunk_document(
    project_id: int,
    document_id: int,
    document_version: int,
    filename: str,
    pages_data: List[Dict[str, Any]],
    chunk_size: int = 500,
    chunk_overlap: int = 100
) -> List[Dict[str, Any]]:
    """
    Splits document pages into chunks with rich automotive metadata.
    """
    chunks = []
    chunk_counter = 0

    for page_item in pages_data:
        page_num = page_item["page"]
        text = page_item["text"]
        headings = page_item.get("headings", [])
        page_default_section = headings[0] if headings else f"Page {page_num}"

        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            # Fallback to lines
            paragraphs = [p.strip() for p in text.splitlines() if p.strip()]

        current_chunk_text = ""
        for p in paragraphs:
            if len(current_chunk_text) + len(p) <= chunk_size:
                current_chunk_text += ("\n\n" if current_chunk_text else "") + p
            else:
                if current_chunk_text:
                    chunk_counter += 1
                    section_title = _detect_chunk_section(current_chunk_text, page_default_section)
                    chunks.append({
                        "chunk_id": f"doc_{document_id}_v{document_version}_c{chunk_counter}",
                        "project_id": project_id,
                        "document_id": document_id,
                        "document_version": document_version,
                        "filename": filename,
                        "page": page_num,
                        "section": section_title,
                        "content": current_chunk_text,
                        "token_count": len(current_chunk_text.split()),
                        "content_type": "text"
                    })
                current_chunk_text = p

        if current_chunk_text:
            chunk_counter += 1
            section_title = _detect_chunk_section(current_chunk_text, page_default_section)
            chunks.append({
                "chunk_id": f"doc_{document_id}_v{document_version}_c{chunk_counter}",
                "project_id": project_id,
                "document_id": document_id,
                "document_version": document_version,
                "filename": filename,
                "page": page_num,
                "section": section_title,
                "content": current_chunk_text,
                "token_count": len(current_chunk_text.split()),
                "content_type": "text"
            })

    return chunks
