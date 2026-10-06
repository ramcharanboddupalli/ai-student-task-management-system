from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from .database import database_session
from .dependencies import get_database_path, require_role
from .services.groq_service import AIConfigurationError, AIRequestError
from . import student_repository, student_service
from .student_schemas import (
    StudentAssistantRequest,
    StudentPracticeGenerateRequest,
    StudentPracticeSubmitRequest,
    StudentStudyPlannerRequest,
    StudentTaskStatusUpdate,
)

router = APIRouter(prefix="/api/v1/student", tags=["student"])


@router.get("/dashboard")
def get_dashboard(
    session=Depends(require_role("student")),
    database_path=Depends(get_database_path),
):
    with database_session(database_path) as connection:
        dashboard = student_repository.student_dashboard(
            connection, int(session["sub"])
        )
    if dashboard is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    dashboard.pop("tasks")
    return dashboard


@router.get("/tasks")
def get_tasks(
    session=Depends(require_role("student")),
    database_path=Depends(get_database_path),
):
    with database_session(database_path) as connection:
        return student_repository.student_tasks(connection, int(session["sub"]))


@router.patch("/tasks/{assignment_id}/status")
def update_task_status(
    assignment_id: int,
    body: StudentTaskStatusUpdate,
    session=Depends(require_role("student")),
    database_path=Depends(get_database_path),
):
    try:
        with database_session(database_path) as connection:
            updated = student_repository.update_student_task_status(
                connection,
                int(session["sub"]),
                assignment_id,
                body.status.value,
            )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if updated is None:
        raise HTTPException(status_code=404, detail="Assigned task not found.")
    return updated


@router.get("/insights/daily")
def get_daily_insight(
    session=Depends(require_role("student")),
    database_path=Depends(get_database_path),
):
    with database_session(database_path) as connection:
        try:
            insight = student_service.daily_insight(
                connection, int(session["sub"])
            )
        except AIConfigurationError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except AIRequestError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
    if insight is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return insight


@router.post("/tasks/prioritization")
def prioritize_tasks(
    session=Depends(require_role("student")),
    database_path=Depends(get_database_path),
):
    with database_session(database_path) as connection:
        tasks = student_repository.student_tasks(connection, int(session["sub"]))
        try:
            return student_service.prioritize_tasks(tasks)
        except AIConfigurationError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except AIRequestError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error


@router.post("/assistant")
def ask_learning_assistant(
    body: StudentAssistantRequest,
    session=Depends(require_role("student")),
    database_path=Depends(get_database_path),
):
    try:
        with database_session(database_path) as connection:
            return student_service.assistant_answer(
                connection, int(session["sub"]), body
            )
    except LookupError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    except AIConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except AIRequestError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.post("/coach")
def get_learning_coach_analysis(
    session=Depends(require_role("student")),
    database_path=Depends(get_database_path),
):
    try:
        with database_session(database_path) as connection:
            return student_service.coach_analysis(connection, int(session["sub"]))
    except LookupError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    except AIConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except AIRequestError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.post("/planner")
def generate_study_plan(
    body: StudentStudyPlannerRequest,
    session=Depends(require_role("student")),
    database_path=Depends(get_database_path),
):
    try:
        with database_session(database_path) as connection:
            return student_service.create_study_plan(
                connection, int(session["sub"]), body
            )
    except LookupError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    except AIConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except AIRequestError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/practice/topics")
def get_practice_topics(
    session=Depends(require_role("student")),
    database_path=Depends(get_database_path),
):
    with database_session(database_path) as connection:
        snapshot = student_repository.student_learning_records(
            connection, int(session["sub"])
        )
    if snapshot is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    topics = sorted(
        {
            str(skill["topic"]) for skill in snapshot["skills"]
        }
        | {str(task["topic"]) for task in snapshot["tasks"]},
        key=str.casefold,
    )
    return {
        "topics": topics,
        "weak_topics": [
            skill["topic"]
            for skill in snapshot["skills"]
            if float(skill["mastery_score"]) < 70
        ],
        "default_difficulty": snapshot["student"]["current_level"],
    }


@router.post("/practice/generate")
def generate_practice_questions(
    body: StudentPracticeGenerateRequest,
    session=Depends(require_role("student")),
    database_path=Depends(get_database_path),
):
    try:
        with database_session(database_path) as connection:
            return student_service.generate_practice(
                connection, int(session["sub"]), body
            )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except LookupError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except AIConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except AIRequestError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.post("/practice/{practice_id}/submit")
def submit_practice_answers(
    practice_id: str,
    body: StudentPracticeSubmitRequest,
    session=Depends(require_role("student")),
    database_path=Depends(get_database_path),
):
    try:
        with database_session(database_path) as connection:
            return student_service.submit_practice(
                connection, int(session["sub"]), practice_id, body
            )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except AIConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except AIRequestError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.post("/report")
def create_student_progress_report(
    session=Depends(require_role("student")),
    database_path=Depends(get_database_path),
):
    try:
        with database_session(database_path) as connection:
            return student_service.generate_progress_report(
                connection, int(session["sub"])
            )
    except LookupError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    except AIConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except AIRequestError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/report/history")
def get_student_progress_reports(
    session=Depends(require_role("student")),
    database_path=Depends(get_database_path),
):
    with database_session(database_path) as connection:
        return student_repository.student_reports(connection, int(session["sub"]))
