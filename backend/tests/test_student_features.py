import asyncio
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Awaitable, Callable

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.database import database_session
from app.main import create_app
from app.seed import DEMO_STUDENTS
from app.student_schemas import (
    GeneratedPracticeQuestion,
    GeneratedPracticeSet,
    PracticeAnswerEvaluation,
    StudentAssistantResponse,
    StudentCoachAnalysis,
    StudentDailyInsight,
    StudentPracticeEvaluation,
    StudentProgressReportAnalysis,
    StudentStudyPlanAdvice,
    StudentTaskPrioritization,
    StudySessionNote,
    TaskPriorityRecommendation,
)


async def with_student_client(
    application: FastAPI,
    test: Callable[[AsyncClient, Path], Awaitable[None]],
    database_path: Path,
) -> None:
    application.state.session_secret = "test-only-session-secret-not-for-production"
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://testserver"
        ) as client:
            response = await client.post(
                "/api/v1/auth/student/login",
                json={
                    "student_id": DEMO_STUDENTS[0][0],
                    "password": "ArjunKumarREG-DA-0001",
                },
            )
            assert response.status_code == 200
            await test(client, database_path)


def test_student_dashboard_and_tasks_are_scoped_to_authenticated_student(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "student.db"

    async def check(client: AsyncClient, _: Path) -> None:
        dashboard_response = await client.get(
            "/api/v1/student/dashboard?student_id=2"
        )
        assert dashboard_response.status_code == 200
        dashboard = dashboard_response.json()
        assert dashboard["student"]["student_id"] == "SKX-DA-0001"
        assert dashboard["student"]["current_level"] == "Beginner"
        assert dashboard["total_tasks"] == 2
        assert dashboard["completed_tasks"] == 1
        assert dashboard["in_progress_tasks"] == 1
        assert dashboard["completion_percentage"] == 50.0
        assert dashboard["today_priority"]["title"] == "Summarize a data trend"
        assert "tasks" not in dashboard

        tasks_response = await client.get("/api/v1/student/tasks")
        assert tasks_response.status_code == 200
        tasks = tasks_response.json()
        assert len(tasks) == 2
        assert {task["title"] for task in tasks} == {
            "Explore a dataset",
            "Summarize a data trend",
        }
        assert all("student_id" not in task for task in tasks)
        assert "Build a reusable Python function" not in tasks_response.text

    asyncio.run(
        with_student_client(create_app(database_path), check, database_path)
    )


def test_student_can_only_update_own_task_through_forward_status_flow(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "status.db"

    async def check(client: AsyncClient, _: Path) -> None:
        with database_session(database_path) as connection:
            own_assignment_id = connection.execute(
                """SELECT id FROM student_tasks
                   WHERE student_id = (SELECT id FROM students WHERE student_id = ?)
                     AND status = 'In Progress'""",
                (DEMO_STUDENTS[0][0],),
            ).fetchone()["id"]
            another_assignment_id = connection.execute(
                """SELECT id FROM student_tasks
                   WHERE student_id = (SELECT id FROM students WHERE student_id = ?)
                   LIMIT 1""",
                (DEMO_STUDENTS[1][0],),
            ).fetchone()["id"]

        other_student = await client.patch(
            f"/api/v1/student/tasks/{another_assignment_id}/status",
            json={"status": "Completed"},
        )
        assert other_student.status_code == 404

        changed = await client.patch(
            f"/api/v1/student/tasks/{own_assignment_id}/status",
            json={"status": "Completed"},
        )
        assert changed.status_code == 200
        assert changed.json()["status"] == "Completed"
        assert changed.json()["completed_at"] is not None

        reverse_transition = await client.patch(
            f"/api/v1/student/tasks/{own_assignment_id}/status",
            json={"status": "In Progress"},
        )
        assert reverse_transition.status_code == 409

        extra_fields = await client.patch(
            f"/api/v1/student/tasks/{own_assignment_id}/status",
            json={"status": "Pending", "student_id": 2, "task_id": 7},
        )
        assert extra_fields.status_code == 422

        assert (
            await client.post(
                f"/api/v1/admin/tasks/{own_assignment_id}/assign",
                json={
                    "student_ids": [1],
                    "deadline": (date.today() + timedelta(days=7)).isoformat(),
                },
            )
        ).status_code == 403
        assert (
            await client.delete(f"/api/v1/admin/tasks/{own_assignment_id}")
        ).status_code == 404

    asyncio.run(
        with_student_client(create_app(database_path), check, database_path)
    )


def test_student_status_flow_allows_start_then_complete(tmp_path: Path) -> None:
    database_path = tmp_path / "forward-flow.db"

    async def check(client: AsyncClient, _: Path) -> None:
        with database_session(database_path) as connection:
            assignment = connection.execute(
                """SELECT id FROM student_tasks
                   WHERE student_id = (SELECT id FROM students WHERE student_id = ?)
                     AND status = 'Completed' LIMIT 1""",
                (DEMO_STUDENTS[0][0],),
            ).fetchone()
            assignment_id = int(assignment["id"])
            connection.execute(
                """UPDATE student_tasks SET status = 'Pending', completed_at = NULL
                   WHERE id = ?""",
                (assignment_id,),
            )

        skipped = await client.patch(
            f"/api/v1/student/tasks/{assignment_id}/status",
            json={"status": "Completed"},
        )
        assert skipped.status_code == 409

        started = await client.patch(
            f"/api/v1/student/tasks/{assignment_id}/status",
            json={"status": "In Progress"},
        )
        assert started.status_code == 200
        assert started.json()["status"] == "In Progress"

        completed = await client.patch(
            f"/api/v1/student/tasks/{assignment_id}/status",
            json={"status": "Completed"},
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "Completed"

    asyncio.run(
        with_student_client(create_app(database_path), check, database_path)
    )


def test_student_cannot_access_student_routes_as_admin(tmp_path: Path) -> None:
    database_path = tmp_path / "admin.db"

    async def check(client: AsyncClient, _: Path) -> None:
        await client.post("/api/v1/auth/logout")
        admin_login = await client.post(
            "/api/v1/auth/admin/signup",
            json={
                "full_name": "Test Administrator",
                "email": "phase3a@example.com",
                "password": "TestOnlyAdminPassword123!",
            },
        )
        assert admin_login.status_code == 201
        for path in (
            "/api/v1/student/dashboard",
            "/api/v1/student/tasks",
            "/api/v1/student/insights/daily",
            "/api/v1/student/tasks/prioritization",
            "/api/v1/student/assistant",
            "/api/v1/student/coach",
            "/api/v1/student/planner",
            "/api/v1/student/practice/topics",
            "/api/v1/student/practice/generate",
            "/api/v1/student/report",
            "/api/v1/student/report/history",
        ):
            method = (
                "post"
                if path.endswith(
                    ("prioritization", "assistant", "coach", "planner", "generate", "report")
                )
                else "get"
            )
            response = await client.request(method, path)
            assert response.status_code == 403

    asyncio.run(
        with_student_client(create_app(database_path), check, database_path)
    )


def test_student_ai_routes_show_unconfigured_state_without_groq_key(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "ai-unconfigured.db"

    async def check(client: AsyncClient, _: Path) -> None:
        insight = await client.get("/api/v1/student/insights/daily")
        prioritization = await client.post(
            "/api/v1/student/tasks/prioritization"
        )
        assert insight.status_code == 503
        assert prioritization.status_code == 503
        assert insight.json()["detail"].startswith("AI features are unavailable")

    asyncio.run(
        with_student_client(create_app(database_path), check, database_path)
    )


def test_student_ai_uses_only_authenticated_students_context(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "student-ai.db"
    from app import student_service

    received_contexts: list[dict[str, object]] = []

    def fake_complete_structured(_system_prompt, user_prompt, response_type):
        context = json.loads(user_prompt)
        received_contexts.append(context)
        if response_type is StudentDailyInsight:
            return StudentDailyInsight(
                headline="Keep your focus on recorded work",
                summary="Your current assignment data indicates one task needs attention.",
                recommended_action="Review the nearest outstanding deadline.",
            )
        if response_type is StudentTaskPrioritization:
            task_ids = [task["assignment_id"] for task in context["tasks"]]
            return StudentTaskPrioritization(
                recommendations=[
                    TaskPriorityRecommendation(
                        assignment_id=task_id,
                        rationale="This order reflects the recorded deadline and status.",
                    )
                    for task_id in task_ids
                ]
            )
        raise AssertionError("Unexpected AI response schema")

    monkeypatch.setattr(
        student_service.groq_service,
        "complete_structured",
        fake_complete_structured,
    )

    async def check(client: AsyncClient, _: Path) -> None:
        dashboard = await client.get("/api/v1/student/dashboard")
        task_ids = {task["assignment_id"] for task in (await client.get(
            "/api/v1/student/tasks"
        )).json() if task["status"] != "Completed"}

        insight = await client.get("/api/v1/student/insights/daily")
        assert insight.status_code == 200
        assert insight.json()["headline"] == "Keep your focus on recorded work"

        prioritization = await client.post(
            "/api/v1/student/tasks/prioritization"
        )
        assert prioritization.status_code == 200
        assert {
            item["assignment_id"]
            for item in prioritization.json()["recommendations"]
        } == task_ids

        assert len(received_contexts) == 2
        assert received_contexts[0]["student"]["full_name"] == dashboard.json()["student"]["full_name"]
        assert {
            task["title"] for task in received_contexts[0]["assigned_tasks"]
        } == {"Explore a dataset", "Summarize a data trend"}
        assert {
            task["assignment_id"] for task in received_contexts[1]["tasks"]
        } == task_ids
        assert all("student_id" not in task for task in received_contexts[1]["tasks"])

    asyncio.run(
        with_student_client(create_app(database_path), check, database_path)
    )


def test_student_prioritization_rejects_unknown_or_missing_assignments(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "invalid-ai.db"
    from app import student_service

    def invalid_response(_system_prompt, user_prompt, response_type):
        task_ids = [task["assignment_id"] for task in json.loads(user_prompt)["tasks"]]
        return response_type(
            recommendations=[
                TaskPriorityRecommendation(
                    assignment_id=task_ids[0] + 1000,
                    rationale="This is not a supplied assignment.",
                )
            ]
        )

    monkeypatch.setattr(
        student_service.groq_service,
        "complete_structured",
        invalid_response,
    )

    async def check(client: AsyncClient, _: Path) -> None:
        response = await client.post("/api/v1/student/tasks/prioritization")
        assert response.status_code == 502
        assert "exactly the supplied" in response.json()["detail"]

    asyncio.run(
        with_student_client(create_app(database_path), check, database_path)
    )


def test_phase03b_student_features_use_real_scoped_context_and_hide_practice_answers(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "phase03b.db"
    from app import student_service

    seen_contexts: list[dict[str, object]] = []

    def fake_complete_structured(_system_prompt, user_prompt, response_type):
        context = json.loads(user_prompt)
        seen_contexts.append(context)
        if response_type is StudentAssistantResponse:
            assert context["student"]["student_id"] == "SKX-DA-0001"
            assert "SKX-PY-0002" not in user_prompt
            assert {task["title"] for task in context["assigned_tasks"]} == {
                "Explore a dataset",
                "Summarize a data trend",
            }
            return StudentAssistantResponse(
                answer="A data trend is a pattern in measurements over time.",
                suggested_questions=["Would a line chart show this trend clearly?"],
            )
        if response_type is StudentCoachAnalysis:
            task_id = context["open_tasks"][0]["assignment_id"]
            topic = context["topic_progress"][0]["topic"]
            return StudentCoachAnalysis(
                strengths=["You have completed an assigned data exploration."],
                weak_areas=["Recorded mastery for data exploration is still developing."],
                learning_gaps=["Continue building confidence interpreting visual trends."],
                progress_trend="One task is completed in the recorded assignment history.",
                recommended_next_topic=topic,
                recommended_next_task_assignment_id=task_id,
                improvement_actions=["Review your recorded data exploration skill."],
                coaching_advice="Use the assigned work to practice interpreting evidence.",
            )
        if response_type is StudentStudyPlanAdvice:
            return StudentStudyPlanAdvice(
                session_notes=[
                    StudySessionNote(
                        assignment_id=item["assignment_id"],
                        study_date=item["study_date"],
                        session_number=item["session_number"],
                        note="Focus this session on the assigned task.",
                    )
                    for item in context["deterministic_schedule"]
                ],
                priority_explanation="The overdue high-priority assignment comes first.",
                study_advice="Take a short break between focused study sessions.",
            )
        if response_type is GeneratedPracticeSet:
            assert context["selected_topic"] == "Data visualization"
            assert context["question_count"] == 2
            return GeneratedPracticeSet(
                questions=[
                    GeneratedPracticeQuestion(
                        question_id=1,
                        question="Which chart best shows a trend over time?",
                        topic=context["selected_topic"],
                        difficulty=context["requested_difficulty"],
                        options=["Line chart", "Pie chart", "Map", "Table"],
                        correct_answer="Line chart",
                        explanation="A line chart makes changes over a continuous timeline visible.",
                    ),
                    GeneratedPracticeQuestion(
                        question_id=2,
                        question="What should a chart title communicate?",
                        topic=context["selected_topic"],
                        difficulty=context["requested_difficulty"],
                        options=["The chart's main subject", "Only its colors", "Nothing", "The author's name"],
                        correct_answer="The chart's main subject",
                        explanation="A clear title identifies the subject or key message.",
                    ),
                ]
            )
        if response_type is StudentPracticeEvaluation:
            assert context["subjective_responses"] == []
            assert len(context["objective_results"]) == 2
            return StudentPracticeEvaluation(
                evaluations=[],
                recommendation="Practice interpreting chart choices with another recorded topic.",
            )
        if response_type is StudentProgressReportAnalysis:
            assert context["deterministic_metrics"]["total_tasks"] == 2
            assert context["deterministic_metrics"]["completed_tasks"] == 1
            return StudentProgressReportAnalysis(
                summary="Your recorded assignments show one completed task and one task still in progress.",
                strengths=["You completed an assigned data exploration task."],
                weak_skills=["Recorded scores show room to improve data exploration."],
                learning_gaps=["Continue practicing data visualization."],
                recommended_topics=["Data visualization"],
                next_skills=["Interpreting chart trends"],
                career_suggestions=["Explore how data analysts communicate findings."],
                overall_recommendation="Focus on completing the active assigned task.",
            )
        raise AssertionError(f"Unexpected AI response schema: {response_type}")

    monkeypatch.setattr(
        student_service.groq_service,
        "complete_structured",
        fake_complete_structured,
    )

    async def check(client: AsyncClient, database: Path) -> None:
        original_tasks = await client.get("/api/v1/student/tasks")
        original_states = {
            task["assignment_id"]: task["status"] for task in original_tasks.json()
        }

        assistant = await client.post(
            "/api/v1/student/assistant",
            json={
                "question": "Explain a data trend simply",
                "conversation": [{"role": "user", "content": "I am learning charts."}],
            },
        )
        assert assistant.status_code == 200
        assert "data trend" in assistant.json()["answer"]

        coach = await client.post("/api/v1/student/coach")
        assert coach.status_code == 200
        assert coach.json()["metrics"]["completion_percentage"] == 50.0
        assert coach.json()["recommended_next_task"]["assignment_id"] is not None

        planner = await client.post(
            "/api/v1/student/planner",
            json={
                "available_minutes_per_day": 60,
                "session_minutes": 30,
                "study_days": [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ],
                "goal": "Finish my overdue visualization assignment",
            },
        )
        assert planner.status_code == 200
        sessions = planner.json()["today_sessions"] + planner.json()["upcoming_sessions"]
        assert sessions
        assert {session["title"] for session in sessions} == {"Summarize a data trend"}
        assert all(0 < session["minutes"] <= 30 for session in sessions)
        scheduled_dates = {session["study_date"] for session in sessions}
        assert all(
            sum(
                session["minutes"]
                for session in sessions
                if session["study_date"] == study_date
            )
            <= 60
            for study_date in scheduled_dates
        )

        topics = await client.get("/api/v1/student/practice/topics")
        assert topics.status_code == 200
        assert topics.json()["topics"] == ["Data exploration", "Data visualization"]
        practice = await client.post(
            "/api/v1/student/practice/generate",
            json={
                "topic": "Data visualization",
                "difficulty": "Beginner",
                "question_count": 2,
                "practice_type": "Multiple Choice",
            },
        )
        assert practice.status_code == 200
        practice_data = practice.json()
        assert "correct_answer" not in practice.text
        assert "explanation" not in practice.text
        evaluated = await client.post(
            f"/api/v1/student/practice/{practice_data['practice_id']}/submit",
            json={
                "answers": [
                    {"question_id": 1, "answer": "Line chart"},
                    {"question_id": 2, "answer": "Only its colors"},
                ]
            },
        )
        assert evaluated.status_code == 200
        assert evaluated.json()["score"] == 50
        assert evaluated.json()["correct_count"] == 1
        assert evaluated.json()["results"][0]["correct_answer"] == "Line chart"
        assert evaluated.json()["results"][1]["explanation"]
        replay = await client.post(
            f"/api/v1/student/practice/{practice_data['practice_id']}/submit",
            json={
                "answers": [
                    {"question_id": 1, "answer": "Line chart"},
                    {"question_id": 2, "answer": "Table"},
                ]
            },
        )
        assert replay.status_code == 404

        report = await client.post("/api/v1/student/report")
        assert report.status_code == 200
        assert report.json()["content"]["metrics"]["total_tasks"] == 2
        assert report.json()["content"]["metrics"]["completed_tasks"] == 1
        assert report.json()["content"]["metrics"]["performance_category"] == "Needs focused practice"
        history = await client.get("/api/v1/student/report/history")
        assert history.status_code == 200
        assert len(history.json()) == 1
        assert history.json()[0]["id"] == report.json()["id"]

        current_tasks = await client.get("/api/v1/student/tasks")
        assert {
            task["assignment_id"]: task["status"] for task in current_tasks.json()
        } == original_states
        with database_session(database) as connection:
            assert connection.execute(
                """SELECT COUNT(*) FROM student_practice_sessions
                   WHERE student_id = 1 AND id = ?""",
                (practice_data["practice_id"],),
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT COUNT(*) FROM reports WHERE report_type = 'student_progress'"
            ).fetchone()[0] == 1

        await client.post("/api/v1/auth/logout")
        second_student = await client.post(
            "/api/v1/auth/student/login",
            json={
                "student_id": DEMO_STUDENTS[1][0],
                "password": "PriyaSharmaREG-PY-0002",
            },
        )
        assert second_student.status_code == 200
        stolen_practice = await client.post(
            f"/api/v1/student/practice/{practice_data['practice_id']}/submit",
            json={
                "answers": [
                    {"question_id": 1, "answer": "Line chart"},
                    {"question_id": 2, "answer": "Table"},
                ]
            },
        )
        assert stolen_practice.status_code == 404
        second_student_history = await client.get("/api/v1/student/report/history")
        assert second_student_history.status_code == 200
        assert second_student_history.json() == []
        assert len(seen_contexts) == 6

    asyncio.run(
        with_student_client(create_app(database_path), check, database_path)
    )


def test_student_short_answer_practice_is_evaluated_by_ai_after_submission(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "short-answer-practice.db"
    from app import student_service

    def fake_complete_structured(_system_prompt, user_prompt, response_type):
        context = json.loads(user_prompt)
        if response_type is GeneratedPracticeSet:
            return GeneratedPracticeSet(
                questions=[
                    GeneratedPracticeQuestion(
                        question_id=1,
                        question="In one sentence, what does a line chart help show?",
                        topic="Data visualization",
                        difficulty="Beginner",
                        options=[],
                        correct_answer="A pattern or change across an ordered sequence such as time.",
                        explanation="Line charts connect ordered values so the direction and pattern are visible.",
                    )
                ]
            )
        if response_type is StudentPracticeEvaluation:
            assert context["subjective_responses"][0]["student_answer"] == (
                "It shows how values change over time."
            )
            return StudentPracticeEvaluation(
                evaluations=[
                    PracticeAnswerEvaluation(
                        question_id=1,
                        score=90,
                        feedback="Correctly identifies how a line chart shows change over time.",
                    )
                ],
                recommendation="Practice describing what a chart's direction means.",
            )
        raise AssertionError(f"Unexpected AI response schema: {response_type}")

    monkeypatch.setattr(
        student_service.groq_service,
        "complete_structured",
        fake_complete_structured,
    )

    async def check(client: AsyncClient, _: Path) -> None:
        generated = await client.post(
            "/api/v1/student/practice/generate",
            json={
                "topic": "Data visualization",
                "difficulty": "Beginner",
                "question_count": 1,
                "practice_type": "Short Answer",
            },
        )
        assert generated.status_code == 200
        assert "correct_answer" not in generated.text
        assert "explanation" not in generated.text
        evaluated = await client.post(
            f"/api/v1/student/practice/{generated.json()['practice_id']}/submit",
            json={
                "answers": [
                    {
                        "question_id": 1,
                        "answer": "It shows how values change over time.",
                    }
                ]
            },
        )
        assert evaluated.status_code == 200
        assert evaluated.json()["score"] == 90
        assert evaluated.json()["results"][0]["correct_answer"]
        assert evaluated.json()["results"][0]["explanation"]

    asyncio.run(
        with_student_client(create_app(database_path), check, database_path)
    )


def test_student_assistant_rejects_unrecorded_percentage_claims(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "unsupported-claim.db"
    from app import student_service

    monkeypatch.setattr(
        student_service.groq_service,
        "complete_structured",
        lambda _system_prompt, _user_prompt, _response_type: StudentAssistantResponse(
            answer="Completing the current task will raise your completion to 66%.",
            suggested_questions=[],
        ),
    )

    async def check(client: AsyncClient, _: Path) -> None:
        response = await client.post(
            "/api/v1/student/assistant",
            json={"question": "What percentage will I reach?"},
        )
        assert response.status_code == 502
        assert "percentage" in response.json()["detail"]

    asyncio.run(
        with_student_client(create_app(database_path), check, database_path)
    )


def test_student_assistant_rejects_recorded_percentage_used_for_unrelated_claim(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "misapplied-percentage.db"
    from app import student_service

    monkeypatch.setattr(
        student_service.groq_service,
        "complete_structured",
        lambda _system_prompt, _user_prompt, _response_type: StudentAssistantResponse(
            answer="Revenue increased by 50% in this illustrative example.",
            suggested_questions=[],
        ),
    )

    async def check(client: AsyncClient, _: Path) -> None:
        response = await client.post(
            "/api/v1/student/assistant",
            json={"question": "Explain how I can summarize a data trend."},
        )
        assert response.status_code == 502
        assert "recorded metric" in response.json()["detail"]

    asyncio.run(
        with_student_client(create_app(database_path), check, database_path)
    )
