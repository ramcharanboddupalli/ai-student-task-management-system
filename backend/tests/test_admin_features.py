import asyncio
from datetime import date, timedelta
from pathlib import Path
from typing import Awaitable, Callable

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.database import database_session
from app.main import create_app
from app.security import verify_password


async def with_admin(
    application: FastAPI, test: Callable[[AsyncClient], Awaitable[None]]
) -> None:
    application.state.session_secret = "test-only-session-secret-not-for-production"
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://testserver"
        ) as client:
            login = await client.post(
                "/api/v1/auth/admin/signup",
                json={
                    "full_name": "Academy Admin",
                    "email": "admin@example.com",
                    "password": "StrongAdminPassword123!",
                },
            )
            assert login.status_code == 201
            await test(client)


def test_admin_management_workflows_and_ai_missing_key(tmp_path: Path) -> None:
    database_path = tmp_path / "admin.db"

    async def check(client: AsyncClient) -> None:
        short_name = await client.post(
            "/api/v1/admin/students",
            json={
                "registration_number": "REG-DA-0098",
                "full_name": " A ",
                "course": "Data Analytics",
                "batch": "DA-2026-C",
            },
        )
        assert short_name.status_code == 422

        created = await client.post(
            "/api/v1/admin/students",
            json={
                "registration_number": "REG-DA-0099",
                "full_name": "Maya Patel",
                "course": "Data Analytics",
                "batch": "DA-2026-C",
                "current_level": "Beginner",
            },
        )
        assert created.status_code == 201
        created_data = created.json()
        student = created_data["student"]
        password = created_data["initial_password"]
        assert student["student_id"] == "SKX-DA-0005"
        assert password == "MayaPatelREG-DA-0099"
        assert "password_hash" not in student
        with database_session(database_path) as connection:
            stored_hash = connection.execute(
                "SELECT password_hash FROM students WHERE id = ?", (student["id"],)
            ).fetchone()["password_hash"]
        assert password not in stored_hash
        assert verify_password(stored_hash, password)

        duplicate = await client.post(
            "/api/v1/admin/students",
            json={
                "registration_number": "REG-DA-0099",
                "full_name": "Maya Patel",
                "course": "Data Analytics",
                "batch": "DA-2026-C",
            },
        )
        assert duplicate.status_code == 409

        edited = await client.put(
            f"/api/v1/admin/students/{student['id']}",
            json={"batch": "DA-2026-D", "current_level": "Intermediate"},
        )
        assert edited.status_code == 200
        assert edited.json()["student"]["batch"] == "DA-2026-D"
        assert edited.json()["student"]["current_level"] == "Intermediate"
        null_update = await client.put(
            f"/api/v1/admin/students/{student['id']}",
            json={"full_name": None},
        )
        assert null_update.status_code == 422

        deactivated = await client.post(
            f"/api/v1/admin/students/{student['id']}/deactivate"
        )
        assert deactivated.status_code == 200
        student_login = await client.post(
            "/api/v1/auth/student/login",
            json={"student_id": student["student_id"], "password": password},
        )
        assert student_login.status_code == 401
        assert (
            await client.post(f"/api/v1/admin/students/{student['id']}/activate")
        ).status_code == 200
        student_login = await client.post(
            "/api/v1/auth/student/login",
            json={"student_id": student["student_id"], "password": password},
        )
        assert student_login.status_code == 200
        assert (
            await client.get(f"/api/v1/admin/students/{student['id']}")
        ).status_code == 403
        assert (
            await client.get("/api/v1/student/dashboard")
        ).json()["student"]["student_id"] == student["student_id"]
        await client.post("/api/v1/auth/logout")
        admin_login = await client.post(
            "/api/v1/auth/admin/login",
            json={
                "email": "admin@example.com",
                "password": "StrongAdminPassword123!",
            },
        )
        assert admin_login.status_code == 200

        task_response = await client.post(
            "/api/v1/admin/tasks",
            json={
                "title": "Analyze a local dataset",
                "description": "Explore a local dataset and report one evidence-based finding.",
                "requirements": ["Load a CSV", "Cite one calculated result"],
                "expected_outcome": "A short, reproducible analysis.",
                "difficulty": "Intermediate",
                "estimated_minutes": 60,
                "evaluation_criteria": ["Correct calculation", "Clear explanation"],
                "topic": "Data exploration",
                "course": "Data Analytics",
                "priority": "Normal",
            },
        )
        assert task_response.status_code == 201
        task = task_response.json()
        assert task["requirements"] == ["Load a CSV", "Cite one calculated result"]

        recommendations = await client.post(
            f"/api/v1/admin/tasks/{task['id']}/recommendations",
            json={
                "topic": "Data exploration",
                "course": "Data Analytics",
                "level": "Intermediate",
            },
        )
        assert recommendations.status_code == 503
        assigned = await client.post(
            f"/api/v1/admin/tasks/{task['id']}/assign",
            json={
                "student_ids": [student["id"]],
                "deadline": (date.today() + timedelta(days=7)).isoformat(),
            },
        )
        assert assigned.status_code == 200
        assert assigned.json()["assigned_count"] == 1
        past_deadline = await client.post(
            f"/api/v1/admin/tasks/{task['id']}/assign",
            json={
                "student_ids": [student["id"]],
                "deadline": (date.today() - timedelta(days=1)).isoformat(),
            },
        )
        assert past_deadline.status_code == 422

        profile = await client.get(f"/api/v1/admin/students/{student['id']}")
        assert profile.status_code == 200
        assert len(profile.json()["tasks"]) == 1
        assert "password_hash" not in profile.text
        assert "MayaPatelREG-DA-0099" not in profile.text
        assert (
            await client.post(f"/api/v1/admin/students/{student['id']}/ai-profile")
        ).status_code == 503

        dashboard = (await client.get("/api/v1/admin/dashboard")).json()
        assert dashboard["total_students"] == 6
        assert dashboard["active_tasks"] == 7
        assert dashboard["pending_tasks"] == 4
        assert dashboard["overall_performance"] is not None
        assert dashboard["batch_overview"]
        assert dashboard["recent_activity"]
        performance = await client.get("/api/v1/admin/performance")
        assert performance.status_code == 200
        assert {row["classification"] for row in performance.json()} <= {
            "ON TRACK", "NEEDS ATTENTION", "AT RISK"
        }
        maya_performance = next(
            row for row in performance.json() if row["id"] == student["id"]
        )
        assert maya_performance["suggested_action"].startswith("Review the pending")
        assert "overdue" not in maya_performance["suggested_action"].lower()
        filters = await client.get("/api/v1/admin/student-filters")
        assert filters.status_code == 200
        assert "Data Analytics" in filters.json()["courses"]
        assert (
            await client.post("/api/v1/admin/performance/analyze")
        ).status_code == 503
        batches = await client.get("/api/v1/admin/batches")
        assert batches.status_code == 200
        assert any(item["batch"] == "DA-2026-D" for item in batches.json())
        assert (
            await client.post("/api/v1/admin/batches/DA-2026-D/insights")
        ).status_code == 503
        assert (
            await client.get("/api/v1/admin/insights/daily")
        ).status_code == 503
        assert (
            await client.post(
                "/api/v1/admin/copilot",
                json={"question": "Who has overdue tasks?"},
            )
        ).status_code == 503
        unsupported = await client.post(
            "/api/v1/admin/copilot",
            json={"question": "What is the weather today?"},
        )
        assert unsupported.status_code == 422
        assert "I can answer questions" in unsupported.json()["detail"]
        assert (
            await client.post(
                "/api/v1/admin/reports",
                json={"report_type": "weekly"},
            )
        ).status_code == 503
        assert (await client.get("/api/v1/admin/reports")).json() == []
        assert (
            await client.post(
                "/api/v1/admin/tasks/generate",
                json={
                    "topic": "Data exploration",
                    "course": "Data Analytics",
                    "level": "Beginner",
                    "goal": "Inspect a dataset for errors.",
                },
            )
        ).status_code == 503

        deleted = await client.delete(f"/api/v1/admin/students/{student['id']}")
        assert deleted.status_code == 204
        with database_session(database_path) as connection:
            assert connection.execute(
                "SELECT COUNT(*) FROM students WHERE id = ?", (student["id"],)
            ).fetchone()[0] == 0
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

    asyncio.run(with_admin(create_app(database_path), check))
