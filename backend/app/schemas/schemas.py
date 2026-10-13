from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from backend.app.models.models import RoleEnum, ArtifactStatus

# --- AUTH SCHEMAS ---
class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: RoleEnum = RoleEnum.ENGINEER

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    role: RoleEnum
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

# --- PROJECT SCHEMAS ---
class ProjectCreate(BaseModel):
    name: str
    key: str
    description: Optional[str] = None

class ProjectResponse(BaseModel):
    id: int
    name: str
    key: str
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# --- DOCUMENT & RAG SCHEMAS ---
class DocumentResponse(BaseModel):
    id: int
    project_id: int
    filename: str
    file_type: str
    current_version: int
    is_indexed: bool
    total_pages: int
    created_at: datetime

    class Config:
        from_attributes = True

class Citation(BaseModel):
    document_name: str
    page: int
    section: Optional[str] = None
    chunk_id: str
    snippet: str
    confidence: float  # Legacy field: mapped to retrieval_similarity
    retrieval_similarity: Optional[float] = None

class RAGQueryRequest(BaseModel):
    project_id: int
    query: str
    top_k: int = 5
    require_strict_citations: bool = True

class RAGQueryResponse(BaseModel):
    answer: str
    confidence: float  # Legacy compatibility field: overall evidence confidence (0.0 to 1.0)
    evidence_confidence: Optional[float] = None
    primary_similarity: Optional[float] = None
    confidence_note: Optional[str] = None
    citations: List[Citation]
    limitations: str
    disclaimer: str
    audit_id: Optional[int] = None

# --- AUDIT SCHEMAS ---
class AuditLogResponse(BaseModel):
    id: int
    project_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    object_type: str
    object_id: Optional[str] = None
    old_value_json: Optional[Dict[str, Any]] = None
    new_value_json: Optional[Dict[str, Any]] = None
    ai_model: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class HLDAnalysisRequest(BaseModel):
    document_id: int = Field(gt=0)
    version_number: Optional[int] = Field(default=None, gt=0)


class HLDRevisionComparisonRequest(BaseModel):
    before_document_id: int = Field(gt=0)
    before_version_number: int = Field(gt=0)
    after_document_id: int = Field(gt=0)
    after_version_number: int = Field(gt=0)


class HLDFindingReviewRequest(BaseModel):
    reviewed: bool = True
    review_note: Optional[str] = Field(default=None, max_length=2000)
