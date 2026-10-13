from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.models import (
    AuditLog, Document, DocumentChunk, DocumentVersion, HLDReport, Project, User,
)
from backend.app.schemas.schemas import (
    HLDAnalysisRequest, HLDFindingReviewRequest, HLDRevisionComparisonRequest,
)
from backend.app.security.security import get_current_user
from backend.app.services.hld_analysis import analyze_hld, compare_revisions, serialize_report

router = APIRouter(prefix="/hld", tags=["HLD Analysis"])


def _get_project(project_id: int, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _get_document(project_id: int, document_id: int, db: Session) -> Document:
    document = db.query(Document).filter(
        Document.id == document_id, Document.project_id == project_id
    ).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found in this project")
    return document


def _get_revision_chunks(
    project_id: int,
    document: Document,
    version_number: int,
    db: Session,
) -> List[Dict[str, Any]]:
    version = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == document.id,
        DocumentVersion.version_number == version_number,
    ).first()
    if version is None:
        raise HTTPException(status_code=404, detail="Document revision not found")
    rows = db.query(DocumentChunk).filter(
        DocumentChunk.project_id == project_id,
        DocumentChunk.document_id == document.id,
        DocumentChunk.version_number == version_number,
    ).order_by(DocumentChunk.page_number, DocumentChunk.id).all()
    if not rows:
        raise HTTPException(
            status_code=409,
            detail=f"Document revision v{version_number} is not indexed; index it before HLD analysis.",
        )
    return [{
        "document_id": row.document_id,
        "version_number": row.version_number,
        "filename": document.filename,
        "page_number": row.page_number,
        "section_title": row.section_title,
        "chunk_id": row.chunk_id,
        "content": row.content,
    } for row in rows]


def _revision_reference(document: Document, version_number: int) -> Dict[str, Any]:
    return {
        "document_id": document.id,
        "filename": document.filename,
        "version_number": version_number,
    }


def _audit(
    db: Session,
    project_id: int,
    user: User,
    action: str,
    report: HLDReport,
    details: Dict[str, Any],
    citations: List[Dict[str, Any]],
) -> None:
    db.add(AuditLog(
        project_id=project_id,
        user_id=user.id,
        username=user.username,
        action=action,
        object_type="HLD_REPORT",
        object_id=str(report.id),
        new_value_json=details,
        source_references=[
            citation.get("chunk_id") for citation in citations if citation.get("chunk_id")
        ],
    ))


@router.post("/{project_id}/analyze")
def create_hld_analysis(
    project_id: int,
    request: HLDAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_project(project_id, db)
    document = _get_document(project_id, request.document_id, db)
    version_number = request.version_number or document.current_version
    chunks = _get_revision_chunks(project_id, document, version_number, db)
    payload = analyze_hld(chunks)
    payload["source_revision"] = _revision_reference(document, version_number)
    report = HLDReport(
        project_id=project_id,
        report_type="analysis",
        title=f"HLD analysis: {document.filename} v{version_number}",
        document_references=[_revision_reference(document, version_number)],
        payload=payload,
        created_by_id=current_user.id,
    )
    db.add(report)
    db.flush()
    _audit(
        db, project_id, current_user, "HLD_ANALYSIS_GENERATED", report,
        {"report_type": report.report_type, "document_references": report.document_references},
        [citation for component in payload["components"] for citation in component["citations"]],
    )
    db.commit()
    db.refresh(report)
    return {"id": report.id, "report_type": report.report_type, "payload": report.payload}


@router.post("/{project_id}/compare")
def create_revision_comparison(
    project_id: int,
    request: HLDRevisionComparisonRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_project(project_id, db)
    before_document = _get_document(project_id, request.before_document_id, db)
    after_document = _get_document(project_id, request.after_document_id, db)
    before_chunks = _get_revision_chunks(
        project_id, before_document, request.before_version_number, db
    )
    after_chunks = _get_revision_chunks(
        project_id, after_document, request.after_version_number, db
    )
    before_reference = _revision_reference(before_document, request.before_version_number)
    after_reference = _revision_reference(after_document, request.after_version_number)
    payload = compare_revisions(
        before_chunks, after_chunks, before_reference, after_reference
    )
    report = HLDReport(
        project_id=project_id,
        report_type="revision_comparison",
        title=(
            f"Revision comparison: {before_document.filename} v{request.before_version_number} "
            f"to {after_document.filename} v{request.after_version_number}"
        ),
        document_references=[before_reference, after_reference],
        payload=payload,
        created_by_id=current_user.id,
    )
    db.add(report)
    db.flush()
    citations = [
        citation for change in payload["changes"] for citation in change["citations"]
    ]
    _audit(
        db, project_id, current_user, "HLD_REVISIONS_COMPARED", report,
        {"document_references": report.document_references, "change_count": len(payload["changes"])},
        citations,
    )
    db.commit()
    db.refresh(report)
    return {"id": report.id, "report_type": report.report_type, "payload": report.payload}


@router.get("/{project_id}/reports")
def list_hld_reports(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_project(project_id, db)
    reports = db.query(HLDReport).filter(
        HLDReport.project_id == project_id
    ).order_by(HLDReport.created_at.desc()).all()
    return [{
        "id": item.id,
        "report_type": item.report_type,
        "title": item.title,
        "document_references": item.document_references,
        "created_at": item.created_at,
    } for item in reports]


@router.get("/{project_id}/reports/{report_id}")
def get_hld_report(
    project_id: int,
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_project(project_id, db)
    report = db.query(HLDReport).filter(
        HLDReport.id == report_id, HLDReport.project_id == project_id
    ).first()
    if report is None:
        raise HTTPException(status_code=404, detail="HLD report not found")
    return {
        "id": report.id,
        "report_type": report.report_type,
        "title": report.title,
        "document_references": report.document_references,
        "payload": report.payload,
        "created_at": report.created_at,
    }


@router.patch("/{project_id}/reports/{report_id}/findings/{finding_id}")
def review_hld_finding(
    project_id: int,
    report_id: int,
    finding_id: str,
    request: HLDFindingReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_project(project_id, db)
    report = db.query(HLDReport).filter(
        HLDReport.id == report_id, HLDReport.project_id == project_id
    ).first()
    if report is None:
        raise HTTPException(status_code=404, detail="HLD report not found")
    payload = dict(report.payload)
    collection = "inconsistencies" if report.report_type == "analysis" else "changes"
    records = list(payload.get(collection, []))
    id_key = "finding_id" if collection == "inconsistencies" else "change_id"
    item_index = next(
        (index for index, item in enumerate(records) if item.get(id_key) == finding_id),
        None,
    )
    if item_index is None:
        raise HTTPException(status_code=404, detail="Finding not found in this report")
    item = dict(records[item_index])
    previous_status = item.get("engineering_review_status", "PENDING_ENGINEERING_REVIEW")
    item["engineering_review_status"] = (
        "REVIEWED" if request.reviewed else "PENDING_ENGINEERING_REVIEW"
    )
    item["review_note"] = request.review_note
    records[item_index] = item
    payload[collection] = records
    report.payload = payload
    _audit(
        db, project_id, current_user, "HLD_FINDING_REVIEW_STATUS_UPDATED", report,
        {
            "finding_id": finding_id,
            "old_status": previous_status,
            "new_status": item["engineering_review_status"],
            "review_note": request.review_note,
        },
        item.get("citations", []),
    )
    db.commit()
    return {
        "report_id": report.id,
        "finding_id": finding_id,
        "engineering_review_status": item["engineering_review_status"],
        "review_note": item["review_note"],
    }


@router.get("/{project_id}/reports/{report_id}/export")
def export_hld_report(
    project_id: int,
    report_id: int,
    format: str = Query(default="json", pattern="^(json|csv)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_project(project_id, db)
    report = db.query(HLDReport).filter(
        HLDReport.id == report_id, HLDReport.project_id == project_id
    ).first()
    if report is None:
        raise HTTPException(status_code=404, detail="HLD report not found")
    body, media_type = serialize_report(report.payload, format)
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="hld-report-{report.id}.{format}"'},
    )
