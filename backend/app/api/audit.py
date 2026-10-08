from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.models import AuditLog, User
from backend.app.schemas.schemas import AuditLogResponse
from backend.app.security.security import get_current_user

router = APIRouter(prefix="/audit", tags=["Audit Logs"])

@router.get("/{project_id}", response_model=List[AuditLogResponse])
def get_audit_trail(
    project_id: int,
    action_filter: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(AuditLog).filter(AuditLog.project_id == project_id)
    if action_filter:
        query = query.filter(AuditLog.action == action_filter)
    return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
