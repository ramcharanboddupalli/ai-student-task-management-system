import asyncio
from pathlib import Path
from typing import Awaitable, Callable

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from app.database import database_session, initialize_database
from app.config import Settings
from app.main import create_app
from app.security import generate_initial_password, hash_password, verify_password
from app.seed import seed_demo_data


async def with_client(
    application: FastAPI, test: Callable[[AsyncClient], Awaitable[None]]
) -> None:
    application.state.session_secret = "test-only-session-secret-not-for-production"
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://testserver"
        ) as client:
            await test(client)


def test_health_and_database_health(tmp_path: Path) -> None:
    async def check(client: AsyncClient) -> None:
        health = await client.get("/api/v1/health")
        database_health = await client.get("/api/v1/health/database")
        ai_health = await client.get("/api/v1/health/ai")
        assert health.json() == {"status": "ok"}
        assert database_health.json() == {"status": "ok"}
        assert isinstance(ai_health.json()["configured"], bool)
        assert set(ai_health.json()) == {"configured"}

    asyncio.run(with_client(create_app(tmp_path / "test.db"), check))


def test_startup_requires_a_session_secret(tmp_path: Path) -> None:
    application = create_app(tmp_path / "test.db")
    with pytest.raises(RuntimeError, match="SESSION_SECRET must be configured"):
        asyncio.run(application.router.lifespan_context(application).__aenter__())


def test_environment_placeholders_are_not_treated_as_configured_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SESSION_SECRET", "CHANGE_ME_TO_A_LONG_RANDOM_SECRET")
    monkeypatch.setenv("GROQ_API_KEY", "PASTE_YOUR_GROQ_API_KEY_HERE")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setenv("COOKIE_SECURE", "false")

    settings = Settings.from_environment()

    assert settings.session_secret is None
    assert settings.groq_api_key is None
    assert settings.groq_model == "openai/gpt-oss-120b"
    assert settings.cookie_secure is False


def test_admin_first_signup_login_and_role_protection(tmp_path: Path) -> None:
    async def check(client: AsyncClient) -> None:
        invalid_login = await client.post(
            "/api/v1/auth/admin/login",
            json={"email": "admin@example.com", "password": "incorrect-password"},
        )
        assert invalid_login.status_code == 401
        signup = await client.post(
            "/api/v1/auth/admin/signup",
            json={
                "full_name": "Demo Admin",
                "email": "admin@example.com",
                "password": "VerySecurePass123!",
            },
        )
        assert signup.status_code == 201
        assert signup.json()["role"] == "admin"
        session_cookie = client.cookies.get("skillonex_session")
        assert session_cookie
        assert "skillonex_session=" in signup.headers["set-cookie"]
        assert "httponly" in signup.headers["set-cookie"].lower()
        assert "samesite=strict" in signup.headers["set-cookie"].lower()
        dashboard = await client.get("/api/v1/admin/dashboard")
        assert dashboard.status_code == 200
        assert dashboard.json()["total_students"] == 5
        assert dashboard.json()["active_tasks"] == 6
        assert dashboard.json()["pending_tasks"] == 3
        assert dashboard.json()["in_progress_tasks"] == 3
        assert dashboard.json()["completed_tasks"] == 4
        assert dashboard.json()["completion_rate"] == 40.0
        assert (await client.get("/api/v1/student/dashboard")).status_code == 403

        stale_token = client.cookies.get("skillonex_session")
        assert stale_token
        logout = await client.post("/api/v1/auth/logout")
        assert logout.status_code == 204
        stale_request = await client.get(
            "/api/v1/admin/dashboard",
            headers={"cookie": f"skillonex_session={stale_token}"},
        )
        assert stale_request.status_code == 401
        login = await client.post(
            "/api/v1/auth/admin/login",
            json={"email": "admin@example.com", "password": "VerySecurePass123!"},
        )
        assert login.status_code == 200
        wrong_password = await client.post(
            "/api/v1/auth/admin/login",
            json={"email": "admin@example.com", "password": "WrongPassword123!"},
        )
        assert wrong_password.status_code == 401
        assert (await client.get("/api/v1/auth/me")).json()["role"] == "admin"

        rejected = await client.post(
            "/api/v1/auth/admin/signup",
            json={
                "full_name": "Second Admin",
                "email": "second@example.com",
                "password": "AnotherSecure123!",
            },
        )
        assert rejected.status_code == 409

    asyncio.run(with_client(create_app(tmp_path / "test.db"), check))


def test_student_login_is_scoped_to_authenticated_student(tmp_path: Path) -> None:
    database_path = tmp_path / "test.db"
    async def check(client: AsyncClient) -> None:
        await client.post(
            "/api/v1/auth/admin/signup",
            json={
                "full_name": "Demo Admin",
                "email": "admin@example.com",
                "password": "VerySecurePass123!",
            },
        )
        await client.post("/api/v1/auth/logout")
        invalid_login = await client.post(
            "/api/v1/auth/student/login",
            json={"student_id": "SKX-DA-0001", "password": "incorrect-password"},
        )
        assert invalid_login.status_code == 401
        response = await client.post(
            "/api/v1/auth/student/login",
            json={
                "student_id": "SKX-DA-0001",
                "password": "ArjunKumarREG-DA-0001",
            },
        )
        assert response.status_code == 200
        student_token = client.cookies.get("skillonex_session")
        assert student_token
        dashboard = await client.get("/api/v1/student/dashboard")
        assert dashboard.status_code == 200
        assert dashboard.json()["student"]["student_id"] == "SKX-DA-0001"
        assert dashboard.json()["total_tasks"] == 2
        assert dashboard.json()["completed_tasks"] == 1
        assert dashboard.json()["completion_percentage"] == 50.0
        other_id_query = await client.get("/api/v1/student/dashboard?student_id=2")
        assert other_id_query.json()["student"]["student_id"] == "SKX-DA-0001"
        assert (await client.get("/api/v1/admin/dashboard")).status_code == 403
        await client.post("/api/v1/auth/logout")
        await client.post(
            "/api/v1/auth/admin/login",
            json={"email": "admin@example.com", "password": "VerySecurePass123!"},
        )
        with database_session(database_path) as connection:
            student_db_id = connection.execute(
                "SELECT id FROM students WHERE student_id = 'SKX-DA-0001'"
            ).fetchone()["id"]
        assert (
            await client.post(f"/api/v1/admin/students/{student_db_id}/deactivate")
        ).status_code == 200
        assert (
            await client.get(
                "/api/v1/student/dashboard",
                headers={"cookie": f"skillonex_session={student_token}"},
            )
        ).status_code == 401

    asyncio.run(with_client(create_app(database_path), check))


def test_password_hashing_and_initial_credential_generation() -> None:
    initial_password = generate_initial_password("Priya Sharma", "REG-PY-0002")
    assert initial_password == "PriyaSharmaREG-PY-0002"
    assert initial_password == generate_initial_password("Priya Sharma", "REG-PY-0002")
    stored_hash = hash_password(initial_password)
    assert initial_password not in stored_hash
    assert verify_password(stored_hash, initial_password)
    assert not verify_password(stored_hash, "wrong password")


def test_demo_seed_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "seed.db"
    initialize_database(database_path)
    seed_demo_data(database_path)
    seed_demo_data(database_path)
    with database_session(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 5
        assert connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 5
        assert connection.execute("SELECT COUNT(*) FROM student_tasks").fetchone()[0] == 10
        assert connection.execute("SELECT COUNT(*) FROM student_skills").fetchone()[0] == 10
        password_hashes = connection.execute(
            "SELECT password_hash FROM students"
        ).fetchall()
        assert len(password_hashes) == 5
        assert all(row["password_hash"].startswith("$argon2id$") for row in password_hashes)
