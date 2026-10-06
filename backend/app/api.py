from __future__ import annotations

import logging
import sqlite3
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field, field_validator

from .database import database_session
from .repositories import (
    count_admins,
    create_admin,
    find_admin_by_email,
    find_student_by_login,
)
from .dependencies import get_current_session, get_database_path, require_role
from .security import (
    SESSION_MAX_AGE_SECONDS,
    create_session_token,
    hash_password,
    hash_session_token,
    read_session_token,
    verify_password,
)
from .services.groq_service import groq_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")
SESSION_COOKIE = "skillonex_session"


class AdminSignup(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Full name must contain at least two non-space characters.")
        return normalized


class AdminLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class StudentLogin(BaseModel):
    student_id: str = Field(min_length=4, max_length=40)
    password: str = Field(min_length=1, max_length=128)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/database")
def database_health(database_path=Depends(get_database_path)) -> dict[str, str]:
    try:
        with database_session(database_path) as connection:
            connection.execute("SELECT 1").fetchone()
    except (OSError, sqlite3.Error):
        logger.exception("Database health check failed.")
        raise HTTPException(status_code=503, detail="Database unavailable.")
    return {"status": "ok"}


@router.get("/health/ai")
def ai_health() -> dict[str, bool]:
    return {"configured": groq_service.is_configured}


@router.post("/auth/admin/signup", status_code=status.HTTP_201_CREATED)
def admin_signup(
    request: Request,
    body: AdminSignup,
    response: Response,
    database_path=Depends(get_database_path),
) -> dict[str, object]:
    try:
        with database_session(database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            if count_admins(connection) > 0:
                raise HTTPException(status_code=409, detail="Admin signup is closed.")
            admin = create_admin(
                connection,
                body.full_name.strip(),
                str(body.email).lower(),
                hash_password(body.password),
            )
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=409, detail="Admin account already exists.") from error
    _set_session(request, response, int(admin["id"]), "admin", database_path)
    return {"id": admin["id"], "full_name": admin["full_name"], "email": admin["email"], "role": "admin"}


@router.post("/auth/admin/login")
def admin_login(
    request: Request,
    body: AdminLogin,
    response: Response,
    database_path=Depends(get_database_path),
) -> dict[str, object]:
    with database_session(database_path) as connection:
        admin = find_admin_by_email(connection, str(body.email).lower())
    if admin is None or not verify_password(admin["password_hash"], body.password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    _set_session(request, response, int(admin["id"]), "admin", database_path)
    return {"id": admin["id"], "full_name": admin["full_name"], "email": admin["email"], "role": "admin"}


@router.post("/auth/student/login")
def student_login(
    request: Request,
    body: StudentLogin,
    response: Response,
    database_path=Depends(get_database_path),
) -> dict[str, object]:
    with database_session(database_path) as connection:
        student = find_student_by_login(connection, body.student_id.strip())
    if (
        student is None
        or not student["is_active"]
        or not verify_password(student["password_hash"], body.password)
    ):
        raise HTTPException(status_code=401, detail="Invalid student ID or password.")
    _set_session(request, response, int(student["id"]), "student", database_path)
    return {
        "id": student["id"],
        "student_id": student["student_id"],
        "full_name": student["full_name"],
        "role": "student",
    }


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, database_path=Depends(get_database_path)) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        session = read_session_token(request.app.state.session_secret, token)
        if session:
            with database_session(database_path) as connection:
                connection.execute(
                    """UPDATE sessions SET revoked_at = CURRENT_TIMESTAMP
                       WHERE token_hash = ? AND revoked_at IS NULL""",
                    (hash_session_token(token),),
                )
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=request.app.state.cookie_secure,
        samesite="strict",
    )


@router.get("/auth/me")
def current_user(session=Depends(get_current_session), database_path=Depends(get_database_path)):
    with database_session(database_path) as connection:
        if session["role"] == "admin":
            user = connection.execute(
                "SELECT id, full_name, email FROM admins WHERE id = ?", (session["sub"],)
            ).fetchone()
        else:
            user = connection.execute(
                "SELECT id, student_id, full_name FROM students WHERE id = ? AND is_active = 1",
                (session["sub"],),
            ).fetchone()
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return {**dict(user), "role": session["role"]}


def _set_session(
    request: Request,
    response: Response,
    user_id: int,
    role: str,
    database_path,
) -> None:
    token = create_session_token(request.app.state.session_secret, user_id, role)
    with database_session(database_path) as connection:
        connection.execute(
            "DELETE FROM sessions WHERE expires_at <= CAST(strftime('%s', 'now') AS INTEGER)"
        )
        connection.execute(
            """INSERT INTO sessions (token_hash, user_id, role, expires_at)
               VALUES (?, ?, ?, ?)""",
            (
                hash_session_token(token),
                user_id,
                role,
                int(time.time()) + SESSION_MAX_AGE_SECONDS,
            ),
        )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=request.app.state.cookie_secure,
        samesite="strict",
        path="/",
    )
