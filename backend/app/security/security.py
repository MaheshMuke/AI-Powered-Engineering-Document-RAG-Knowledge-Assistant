import os
import re
from datetime import datetime, timedelta
from typing import Optional, List
import jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models.models import User, RoleEnum

security_bearer = HTTPBearer(auto_error=False)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def sanitize_input_for_prompt_injection(user_input: str) -> str:
    """
    Guards against prompt injection attacks.
    Neutralizes jailbreak attempts and instructions inside uploaded content.
    """
    injection_patterns = [
        r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
        r"system\s+prompt",
        r"reveal\s+(the\s+)?(secret|key|password|system)",
        r"you\s+are\s+now\s+in\s+(developer|unrestricted|god)\s+mode",
        r"disregard\s+all\s+rules",
        r"<script.*?>.*?</script>"
    ]
    sanitized = user_input
    for pat in injection_patterns:
        if re.search(pat, sanitized, re.IGNORECASE):
            sanitized = re.sub(
                pat,
                "[POTENTIAL_INJECTION_PATTERN_FILTERED]",
                sanitized,
                flags=re.IGNORECASE
            )
    return sanitized

def validate_safe_filename(filename: str) -> str:
    """Protects against path traversal attacks."""
    basename = os.path.basename(filename)
    clean_name = re.sub(r"[^\w\.\-_]", "_", basename)
    if clean_name.startswith("..") or "/" in clean_name or "\\" in clean_name:
        raise ValueError("Invalid path traversal filename detected")
    return clean_name

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user

def require_role(allowed_roles: List[RoleEnum]):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role == RoleEnum.ADMIN:
            return current_user  # Admin has access to all
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: User role '{current_user.role}' does not have sufficient permission. Required: {[r.value for r in allowed_roles]}"
            )
        return current_user
    return role_checker
