import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.app.database import engine, Base, SessionLocal
from backend.app.models.models import User, RoleEnum, Project
from backend.app.security.security import get_password_hash

# Import API routers
from backend.app.api.auth import router as auth_router
from backend.app.api.projects import router as projects_router
from backend.app.api.documents import router as documents_router
from backend.app.api.rag import router as rag_router
from backend.app.api.audit import router as audit_router
from backend.app.api.hld import router as hld_router

# Initialize DB Tables
Base.metadata.create_all(bind=engine)

def seed_initial_data():
    """Seeds default accounts and demo project if database is brand new."""
    db = SessionLocal()
    try:
        # 1. Seed Users
        if db.query(User).count() == 0:
            users_to_seed = [
                ("admin", "admin@automotive.internal", "AdminPass123!", "Lead Systems Architect", RoleEnum.ADMIN),
                ("engineer", "engineer@automotive.internal", "EngineerPass123!", "ADAS Systems Engineer", RoleEnum.ENGINEER),
                ("reviewer", "reviewer@automotive.internal", "ReviewerPass123!", "Technical Lead Reviewer", RoleEnum.REVIEWER),
                ("viewer", "viewer@automotive.internal", "ViewerPass123!", "Engineering Auditor", RoleEnum.VIEWER),
            ]
            for uname, email, pwd, fname, role in users_to_seed:
                u = User(
                    username=uname,
                    email=email,
                    hashed_password=get_password_hash(pwd),
                    full_name=fname,
                    role=role
                )
                db.add(u)
            db.commit()

        # 2. Seed Default Project
        admin_user = db.query(User).filter(User.username == "admin").first()
        if db.query(Project).count() == 0 and admin_user:
            demo_proj = Project(
                name="Demo ADAS ECU",
                key="ADAS-01",
                description="Advanced Driver Assistance System with Camera, Perception, and Vehicle Control ECUs.",
                created_by_id=admin_user.id
            )
            db.add(demo_proj)
            db.commit()
    finally:
        db.close()

seed_initial_data()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Engineering Document RAG Knowledge Assistant with grounded hybrid retrieval, citation tracing, and project isolation."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
api_prefix = settings.API_V1_STR
app.include_router(auth_router, prefix=api_prefix)
app.include_router(projects_router, prefix=api_prefix)
app.include_router(documents_router, prefix=api_prefix)
app.include_router(rag_router, prefix=api_prefix)
app.include_router(audit_router, prefix=api_prefix)
app.include_router(hld_router, prefix=api_prefix)

@app.get("/")
def root():
    return {
        "platform": settings.PROJECT_NAME,
        "version": "1.0.0",
        "status": "OPERATIONAL",
        "disclaimer": settings.AI_DISCLAIMER
    }

@app.get("/health")
def health():
    return {"status": "HEALTHY"}
