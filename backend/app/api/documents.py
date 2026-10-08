import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models.models import Document, DocumentVersion, DocumentChunk, Project, User, RoleEnum, AuditLog
from backend.app.schemas.schemas import DocumentResponse
from backend.app.security.security import get_current_user, require_role, validate_safe_filename
from backend.app.ingestion.extractor import extract_document
from backend.app.ingestion.chunker import chunk_document
from backend.app.rag.vector_store import vector_store

router = APIRouter(prefix="/documents", tags=["Documents"])

@router.get("/", response_model=List[DocumentResponse])
def list_documents(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(Document).filter(Document.project_id == project_id).all()

@router.post("/upload", response_model=DocumentResponse)
def upload_document(
    project_id: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(require_role([RoleEnum.ADMIN, RoleEnum.ENGINEER])),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    safe_name = validate_safe_filename(file.filename)
    project_dir = os.path.join(settings.UPLOAD_DIR, f"project_{project_id}")
    os.makedirs(project_dir, exist_ok=True)
    saved_path = os.path.join(project_dir, safe_name)

    # Save file
    with open(saved_path, "wb") as f:
        f.write(file.file.read())

    ext = os.path.splitext(safe_name)[1].lower().replace(".", "")

    # Check if document already exists
    doc = db.query(Document).filter(Document.project_id == project_id, Document.filename == safe_name).first()
    if doc:
        doc.current_version += 1
        doc.file_path = saved_path
        version = DocumentVersion(
            document_id=doc.id,
            version_number=doc.current_version,
            file_path=saved_path,
            uploaded_by_id=current_user.id
        )
        db.add(version)
    else:
        doc = Document(
            project_id=project_id,
            filename=safe_name,
            file_type=ext,
            file_path=saved_path,
            current_version=1,
            is_indexed=False,
            created_by_id=current_user.id
        )
        db.add(doc)
        db.flush()
        version = DocumentVersion(
            document_id=doc.id,
            version_number=1,
            file_path=saved_path,
            uploaded_by_id=current_user.id
        )
        db.add(version)

    audit = AuditLog(
        project_id=project_id,
        user_id=current_user.id,
        username=current_user.username,
        action="DOCUMENT_UPLOADED",
        object_type="DOCUMENT",
        object_id=str(doc.id),
        new_value_json={"filename": safe_name, "version": doc.current_version}
    )
    db.add(audit)
    db.commit()
    db.refresh(doc)
    return doc

@router.post("/{document_id}/index")
def index_document(
    document_id: int,
    current_user: User = Depends(require_role([RoleEnum.ADMIN, RoleEnum.ENGINEER])),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Extract text per page
    pages_data = extract_document(doc.file_path, doc.file_type)
    doc.total_pages = len(pages_data)

    # Chunk text
    chunks = chunk_document(
        project_id=doc.project_id,
        document_id=doc.id,
        document_version=doc.current_version,
        filename=doc.filename,
        pages_data=pages_data
    )

    # Delete existing chunks for this document version
    db.query(DocumentChunk).filter(
        DocumentChunk.document_id == doc.id,
        DocumentChunk.version_number == doc.current_version
    ).delete()

    # Save chunks to DB
    for c in chunks:
        chunk_obj = DocumentChunk(
            project_id=doc.project_id,
            document_id=doc.id,
            version_number=doc.current_version,
            chunk_id=c["chunk_id"],
            page_number=c["page"],
            section_title=c.get("section", ""),
            content=c["content"],
            token_count=c.get("token_count", 0)
        )
        db.add(chunk_obj)

    # Add to ChromaDB vector store
    vector_store.add_chunks(project_id=doc.project_id, chunks=chunks)

    doc.is_indexed = True

    audit = AuditLog(
        project_id=doc.project_id,
        user_id=current_user.id,
        username=current_user.username,
        action="DOCUMENT_INDEXED",
        object_type="DOCUMENT",
        object_id=str(doc.id),
        new_value_json={"chunks_indexed": len(chunks), "total_pages": doc.total_pages}
    )
    db.add(audit)
    db.commit()

    return {
        "status": "SUCCESS",
        "document_id": doc.id,
        "filename": doc.filename,
        "chunks_indexed": len(chunks),
        "total_pages": doc.total_pages
    }
