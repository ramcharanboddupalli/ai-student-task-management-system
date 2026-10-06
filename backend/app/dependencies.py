from __future__ import annotations

from typing import Annotated, Callable

from fastapi import Depends, HTTPException, Request, status

from .database import database_session
from .security import hash_session_token, read_session_token


def get_database_path(request: Request):
    return request.app.state.database_path


def get_current_session(request: Request) -> dict[str, int | str]:
    token = request.cookies.get("skillonex_session")
    secret = request.app.state.session_secret
    session = read_session_token(secret, token) if token else None
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    with database_session(request.app.state.database_path) as connection:
        active_session = connection.execute(
            """SELECT 1 FROM sessions WHERE token_hash = ? AND user_id = ?
               AND role = ? AND expires_at > CAST(strftime('%s', 'now') AS INTEGER)
               AND revoked_at IS NULL""",
            (hash_session_token(token), session["sub"], session["role"]),
        ).fetchone()
        if active_session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required.",
            )
        if session["role"] == "student":
            active_student = connection.execute(
                "SELECT 1 FROM students WHERE id = ? AND is_active = 1",
                (session["sub"],),
            ).fetchone()
            if active_student is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required.",
                )
    return session


def require_role(role: str) -> Callable:
    def dependency(session: Annotated[dict[str, int | str], Depends(get_current_session)]):
        if session["role"] != role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
        return session

    return dependency
