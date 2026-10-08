from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.models import Project, ProjectMember, User, RoleEnum, AuditLog
from backend.app.schemas.schemas import ProjectCreate, ProjectResponse
from backend.app.security.security import get_current_user, require_role

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.get("/", response_model=List[ProjectResponse])
def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(Project).all()

@router.post("/", response_model=ProjectResponse)
def create_project(
    project_in: ProjectCreate,
    current_user: User = Depends(require_role([RoleEnum.ADMIN, RoleEnum.ENGINEER])),
    db: Session = Depends(get_db)
):
    existing = db.query(Project).filter(Project.key == project_in.key.upper()).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Project key '{project_in.key}' already exists")

    project = Project(
        name=project_in.name,
        key=project_in.key.upper(),
        description=project_in.description,
        created_by_id=current_user.id
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    # Add creator as ADMIN member of project
    member = ProjectMember(project_id=project.id, user_id=current_user.id, role=current_user.role)
    db.add(member)

    audit = AuditLog(
        project_id=project.id,
        user_id=current_user.id,
        username=current_user.username,
        action="PROJECT_CREATED",
        object_type="PROJECT",
        object_id=str(project.id),
        new_value_json={"name": project.name, "key": project.key}
    )
    db.add(audit)
    db.commit()

    return project

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
