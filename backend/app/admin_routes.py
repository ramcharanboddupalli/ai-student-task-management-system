from __future__ import annotations

import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, status

from . import admin_repository as repository
from .admin_schemas import (
    AssignmentRequest,
    CopilotQuestion,
    ReportRequest,
    StudentCreate,
    StudentUpdate,
    TaskCreate,
    TaskDraftRequest,
    TaskRecommendationsRequest,
)
from .admin_service import (
    batch_insight,
    classify_question,
    copilot_answer,
    daily_insight,
    generated_report,
    performance_advice,
    recommend_candidates,
    student_profile_insight,
    task_draft,
)
from .dependencies import get_database_path, require_role
from .database import database_session
from .security import generate_initial_password, hash_password
from .services.groq_service import AIConfigurationError, AIRequestError

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    dependencies=[Depends(require_role("admin"))],
)


@router.get("/dashboard")
def get_dashboard(database_path=Depends(get_database_path)):
    with database_session(database_path) as connection:
        return repository.dashboard_data(connection)


@router.get("/insights/daily")
def get_daily_insight(database_path=Depends(get_database_path)):
    with database_session(database_path) as connection:
        try:
            return daily_insight(connection)
        except AIConfigurationError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except AIRequestError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/students")
def get_students(
    search: str | None = Query(default=None, max_length=120),
    course: str | None = Query(default=None, max_length=100),
    batch: str | None = Query(default=None, max_length=80),
    active: bool | None = None,
    database_path=Depends(get_database_path),
):
    with database_session(database_path) as connection:
        return repository.list_students(connection, search, course, batch, active)


@router.get("/student-filters")
def get_student_filters(database_path=Depends(get_database_path)):
    with database_session(database_path) as connection:
        return repository.student_filter_options(connection)


@router.post("/students", status_code=status.HTTP_201_CREATED)
def add_student(body: StudentCreate, database_path=Depends(get_database_path)):
    password = generate_initial_password(body.full_name, body.registration_number)
    try:
        with database_session(database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            student = repository.insert_student(
                connection,
                registration_number=body.registration_number,
                full_name=body.full_name,
                email=str(body.email).lower() if body.email else None,
                course=body.course,
                batch=body.batch,
                current_level=body.current_level.value,
                password_hash=hash_password(password),
            )
    except sqlite3.IntegrityError as error:
        raise HTTPException(
            status_code=409,
            detail="Registration number, email, or generated student ID already exists.",
        ) from error
    return {"student": student, "initial_password": password}


@router.get("/students/{student_id}")
def student_profile(student_id: int, database_path=Depends(get_database_path)):
    with database_session(database_path) as connection:
        profile = repository.get_student_profile(connection, student_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Student not found.")
    return profile


@router.put("/students/{student_id}")
def edit_student(
    student_id: int,
    body: StudentUpdate,
    database_path=Depends(get_database_path),
):
    changes = body.model_dump(exclude_unset=True)
    for key in ("full_name", "course", "batch"):
        if key in changes:
            if changes[key] is None:
                raise HTTPException(status_code=422, detail=f"{key} cannot be null.")
            changes[key] = changes[key].strip()
            if len(changes[key]) < 2:
                raise HTTPException(
                    status_code=422,
                    detail=f"{key} must contain at least two non-space characters.",
                )
    if changes.get("email"):
        changes["email"] = str(changes["email"]).lower()
    if changes.get("current_level"):
        changes["current_level"] = changes["current_level"].value
    try:
        with database_session(database_path) as connection:
            profile = repository.update_student(connection, student_id, changes)
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=409, detail="Email address is already in use.") from error
    if profile is None:
        raise HTTPException(status_code=404, detail="Student not found.")
    return profile


@router.post("/students/{student_id}/deactivate")
def deactivate_student(student_id: int, database_path=Depends(get_database_path)):
    with database_session(database_path) as connection:
        found = repository.set_student_active(connection, student_id, False)
    if not found:
        raise HTTPException(status_code=404, detail="Student not found.")
    return {"status": "deactivated"}


@router.post("/students/{student_id}/activate")
def activate_student(student_id: int, database_path=Depends(get_database_path)):
    with database_session(database_path) as connection:
        found = repository.set_student_active(connection, student_id, True)
    if not found:
        raise HTTPException(status_code=404, detail="Student not found.")
    return {"status": "active"}


@router.delete("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_student(student_id: int, database_path=Depends(get_database_path)):
    with database_session(database_path) as connection:
        deleted = repository.delete_student(connection, student_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Student not found.")


@router.post("/students/{student_id}/ai-profile")
def analyze_student_profile(student_id: int, database_path=Depends(get_database_path)):
    with database_session(database_path) as connection:
        try:
            analysis = student_profile_insight(connection, student_id)
        except AIConfigurationError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except AIRequestError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
    if analysis is None:
        raise HTTPException(status_code=404, detail="Student not found.")
    return analysis


@router.get("/tasks")
def get_tasks(database_path=Depends(get_database_path)):
    with database_session(database_path) as connection:
        return repository.list_tasks(connection)


@router.post("/tasks/generate")
def generate_task(body: TaskDraftRequest):
    try:
        return task_draft(body)
    except AIConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except AIRequestError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(body: TaskCreate, database_path=Depends(get_database_path)):
    try:
        with database_session(database_path) as connection:
            return repository.insert_task(connection, body.model_dump(mode="json"))
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=409, detail="A task with this title already exists for this course.") from error


@router.post("/tasks/{task_id}/recommendations")
def task_recommendations(
    task_id: int,
    body: TaskRecommendationsRequest,
    database_path=Depends(get_database_path),
):
    with database_session(database_path) as connection:
        task = next(
            (item for item in repository.list_tasks(connection) if item["id"] == task_id),
            None,
        )
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        if task["course"] != body.course or task["difficulty"] != body.level.value or task["topic"] != body.topic:
            raise HTTPException(status_code=422, detail="Recommendation context must match the saved task.")
        candidates = repository.task_candidates(connection, body.course, body.level.value, body.topic)
        if not candidates:
            return {"recommendations": [], "message": "No active students match the task course and level."}
        try:
            recommendations = recommend_candidates(
                body.topic, body.course, body.level.value, candidates
            )
        except AIConfigurationError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except AIRequestError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
    return {"recommendations": recommendations, "advisory_only": True}


@router.post("/tasks/{task_id}/assign")
def assign_task(
    task_id: int,
    body: AssignmentRequest,
    database_path=Depends(get_database_path),
):
    try:
        with database_session(database_path) as connection:
            assigned_count = repository.assign_task(
                connection,
                task_id,
                body.student_ids,
                body.deadline.isoformat(),
            )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"assigned_count": assigned_count, "deadline": body.deadline.isoformat()}


@router.get("/performance")
def get_performance(database_path=Depends(get_database_path)):
    with database_session(database_path) as connection:
        return repository.performance_rows(connection)


@router.post("/performance/analyze")
def analyze_performance(database_path=Depends(get_database_path)):
    with database_session(database_path) as connection:
        try:
            return {"students": performance_advice(connection)}
        except AIConfigurationError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except AIRequestError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/batches")
def get_batches(database_path=Depends(get_database_path)):
    with database_session(database_path) as connection:
        return [
            repository.batch_data(connection, batch)
            for batch in repository.batch_names(connection)
        ]


@router.get("/batches/{batch}")
def get_batch(batch: str, database_path=Depends(get_database_path)):
    with database_session(database_path) as connection:
        data = repository.batch_data(connection, batch)
    if data is None:
        raise HTTPException(status_code=404, detail="Batch not found.")
    return data


@router.post("/batches/{batch}/insights")
def analyze_batch(batch: str, database_path=Depends(get_database_path)):
    with database_session(database_path) as connection:
        try:
            insight = batch_insight(connection, batch)
        except AIConfigurationError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except AIRequestError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
    if insight is None:
        raise HTTPException(status_code=404, detail="Batch not found.")
    return insight


@router.post("/copilot")
def ask_copilot(body: CopilotQuestion, database_path=Depends(get_database_path)):
    try:
        classify_question(body.question)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    with database_session(database_path) as connection:
        try:
            return copilot_answer(connection, body.question)
        except AIConfigurationError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except AIRequestError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error


@router.post("/reports", status_code=status.HTTP_201_CREATED)
def create_report(body: ReportRequest, database_path=Depends(get_database_path)):
    try:
        with database_session(database_path) as connection:
            context, report_student_id = repository.report_context(
                connection,
                body.report_type.value,
                body.student_id,
                body.batch,
            )
            content = generated_report(body.report_type.value, context)
            return repository.store_report(
                connection, report_student_id, body.report_type.value, content
            )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except AIConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except AIRequestError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/reports")
def get_reports(database_path=Depends(get_database_path)):
    with database_session(database_path) as connection:
        return repository.list_reports(connection)
