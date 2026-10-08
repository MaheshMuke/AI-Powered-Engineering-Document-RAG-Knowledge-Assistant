from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.models import User, Project
from backend.app.schemas.schemas import RAGQueryRequest, RAGQueryResponse
from backend.app.security.security import get_current_user
from backend.app.rag.rag_engine import rag_engine

router = APIRouter(prefix="/rag", tags=["RAG"])

@router.post("/query", response_model=RAGQueryResponse)
def query_rag(
    req: RAGQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == req.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = rag_engine.query(
        project_id=req.project_id,
        user_query=req.query,
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        top_k=req.top_k
    )
    return result
