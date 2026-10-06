from __future__ import annotations

import json
import logging
import re
import sqlite3
from typing import Any

from pydantic import ValidationError

from .admin_repository import (
    batch_data,
    copilot_context,
    dashboard_data,
    get_student_profile,
    performance_rows,
)
from .admin_schemas import (
    BatchInsights,
    CandidateRecommendations,
    CopilotAnswer,
    GeneratedReport,
    GeneratedTask,
    InsightResponse,
    PerformanceAdvice,
    StudentProfileAnalysis,
    TaskDraftRequest,
)
from .services.groq_service import AIRequestError, groq_service

logger = logging.getLogger(__name__)


def _json(data: Any) -> str:
    return json.dumps(
        data,
        ensure_ascii=True,
        separators=(",", ":"),
        default=_json_default,
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, sqlite3.Row):
        return dict(value)
    raise TypeError(f"Unsupported AI context value: {type(value).__name__}")


def _ai_structured(model: type, system_prompt: str, context: Any):
    try:
        full_prompt = (
            f"{system_prompt}\nOutput JSON schema: {_json(model.model_json_schema())}"
        )
        return groq_service.complete_structured(
            full_prompt,
            _json(context),
            model,
        )
    except ValidationError as error:
        logger.warning("Groq returned invalid structured output (%s).", type(error).__name__)
        raise AIRequestError("The AI response did not match the required format.") from error


def daily_insight(connection: sqlite3.Connection) -> dict[str, Any]:
    dashboard = dashboard_data(connection)
    performance = performance_rows(connection)
    attention = [
        {
            "id": row["id"],
            "student_id": row["student_id"],
            "classification": row["classification"],
            "reasons": row["reasons"],
            "metrics": row["metrics"],
        }
        for row in performance
        if row["classification"] != "ON TRACK"
    ]
    topic_rows = connection.execute(
        """SELECT topic, ROUND(AVG(mastery_score), 1) AS average_mastery,
                  COUNT(*) AS student_count
           FROM student_skills GROUP BY topic ORDER BY average_mastery"""
    ).fetchall()
    context = {
        "metrics": {
            key: dashboard[key]
            for key in (
                "total_students",
                "active_tasks",
                "completion_rate",
                "pending_tasks",
                "overdue_tasks",
                "overall_performance",
            )
        },
        "batches": dashboard["batch_overview"],
        "students_needing_attention": attention,
        "topic_mastery": [dict(row) for row in topic_rows],
        "student_ids": [row["id"] for row in performance],
    }
    response = _ai_structured(
        InsightResponse,
        (
            "You are an academic operations analyst. Interpret only the supplied SQLite facts. "
            "Do not invent, estimate, or recalculate database values. The students_needing_attention "
            "field must contain only IDs from the supplied at-risk records. Identify trends only "
            "when comparisons exist; otherwise say evidence is limited. Return the requested JSON."
        ),
        context,
    )
    allowed_ids = {row["id"] for row in attention}
    if not set(response.students_needing_attention).issubset(allowed_ids):
        raise AIRequestError("The AI response referred to a student outside the supplied records.")
    return response.model_dump()


def task_draft(topic: TaskDraftRequest) -> dict[str, Any]:
    response = _ai_structured(
        GeneratedTask,
        (
            "Create one educational task draft in JSON. Use the provided topic, course, level, "
            "goal, and requirements. Do not claim this task exists or assign it to anyone. "
            "Estimated time must be a realistic integer in minutes. Return only schema-conforming JSON."
        ),
        topic.model_dump(mode="json"),
    )
    if response.difficulty != topic.level:
        raise AIRequestError("The AI task difficulty did not match the requested level.")
    return response.model_dump(mode="json")


def student_profile_insight(
    connection: sqlite3.Connection, student_id: int
) -> dict[str, Any] | None:
    profile = get_student_profile(connection, student_id)
    if profile is None:
        return None
    context = {
        "course": profile["student"]["course"],
        "current_level": profile["student"]["current_level"],
        "metrics": profile["metrics"],
        "recorded_topic_mastery": [
            {"topic": skill["topic"], "mastery_score": skill["mastery_score"]}
            for skill in profile["skills"]
        ],
        "assigned_task_history": [
            {
                "topic": task["topic"],
                "difficulty": task["difficulty"],
                "status": task["status"],
                "performance_score": task["performance_score"],
            }
            for task in profile["tasks"]
        ],
    }
    analysis = _ai_structured(
        StudentProfileAnalysis,
        (
            "Analyze only the supplied student's recorded data. Strengths and weak_areas must be "
            "topic names from recorded_topic_mastery or assigned_task_history. If the records "
            "do not support a claim, omit it. Learning gaps and actions must refer to the supplied "
            "topics or measured metrics. Never change the student's stored level. Return JSON."
        ),
        context,
    )
    topics = {
        skill["topic"].casefold() for skill in profile["skills"]
    } | {task["topic"].casefold() for task in profile["tasks"]}
    if any(
        item.casefold() not in topics
        for item in [*analysis.strengths, *analysis.weak_areas]
    ):
        raise AIRequestError("The AI response referred to an unrecorded learning topic.")
    return {
        "student_id": profile["student"]["student_id"],
        "source": "recorded student tasks, scores, and topic mastery",
        "current_level": profile["student"]["current_level"],
        **analysis.model_dump(),
    }


def recommend_candidates(
    topic: str,
    course: str,
    level: str,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    allowed_ids = {candidate["id"] for candidate in candidates}
    response = _ai_structured(
        CandidateRecommendations,
        (
            "Recommend zero or more candidates for one learning task using only candidate data. "
            "Only return candidate student_id values supplied in the context, no duplicate IDs. "
            "Give a short evidence-based rationale referencing progress/performance/topic mastery. "
            "Recommendations are advisory only; do not create or assign tasks. Return JSON."
        ),
        {
            "task": {"topic": topic, "course": course, "level": level},
            "candidates": candidates,
        },
    )
    recommendations = response.recommendations
    ids = [entry.student_id for entry in recommendations]
    if len(ids) != len(set(ids)) or not set(ids).issubset(allowed_ids):
        raise AIRequestError("The AI response contained an invalid student recommendation.")
    by_id = {candidate["id"]: candidate for candidate in candidates}
    return [
        {
            **by_id[entry.student_id],
            "rationale": entry.rationale,
        }
        for entry in recommendations
    ]


def performance_advice(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = performance_rows(connection)
    response = _ai_structured(
        PerformanceAdvice,
        (
            "Provide concise suggested actions for the supplied students only. Do not calculate "
            "or change metrics/classifications. Return exactly one student_id per supplied record; "
            "student IDs must be copied from the input. Actions must be feasible and evidence-based."
        ),
        rows,
    )
    advice_by_id = {item.student_id: item.suggested_action for item in response.students}
    expected_ids = {row["id"] for row in rows}
    if set(advice_by_id) != expected_ids:
        raise AIRequestError("The AI response did not match the analyzed student records.")
    return [
        {**row, "suggested_action": advice_by_id[row["id"]]}
        for row in rows
    ]


def batch_insight(connection: sqlite3.Connection, batch: str) -> dict[str, Any] | None:
    data = batch_data(connection, batch)
    if data is None:
        return None
    context = {
        key: data[key]
        for key in (
            "batch",
            "student_count",
            "average_completion",
            "average_performance",
            "pending_tasks",
            "overdue_tasks",
            "strong_topics",
            "weak_topics",
            "difficulty_patterns",
            "students_needing_support",
            "weekly_trend",
        )
    }
    analysis = _ai_structured(
        BatchInsights,
        (
            "Interpret only the supplied batch metrics and recorded topics. Do not invent trends "
            "when fewer than two periods are present. Do not invent students or numbers. "
            "Offer concise learning trends and practical recommendations. Return JSON."
        ),
        context,
    )
    return {
        "batch": batch,
        "source": "recorded batch assignments, scores, and topic mastery",
        **analysis.model_dump(),
    }


def copilot_answer(
    connection: sqlite3.Connection, question: str
) -> dict[str, Any]:
    intent = classify_question(question)
    context = copilot_context(connection, intent)
    result = _ai_structured(
        CopilotAnswer,
        (
            "Answer the administrator using only the supplied SQLite query result. Do not invent "
            "students, tasks, dates, metrics, or counts. If there are no records, state that clearly. "
            "Supporting data must be a concise set of facts copied from the records. Return JSON."
        ),
        {"question": question, "query_result": context},
    )
    return {
        **result.model_dump(),
        "data_source": "SQLite records",
        "query_type": intent,
    }


def classify_question(question: str) -> str:
    normalized = re.sub(r"\s+", " ", question.casefold())
    if any(word in normalized for word in ("overdue", "past due", "late task")):
        return "overdue"
    if ("highest" in normalized or "top" in normalized or "best performance" in normalized) and (
        "performance" in normalized or "score" in normalized
    ):
        return "highest_performance"
    if "attention" in normalized or "at risk" in normalized or "risk" in normalized:
        return "needs_attention"
    if any(word in normalized for word in ("pending", "not started")):
        return "pending"
    if "week" in normalized or "weekly" in normalized:
        return "weekly"
    if "batch" in normalized and any(
        word in normalized for word in ("best", "perform", "strong")
    ):
        return "best_batch"
    raise ValueError(
        "I can answer questions about overdue work, highest performance, students needing "
        "attention, pending tasks, weekly summaries, or the best-performing batch."
    )


def generated_report(
    report_type: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    report = _ai_structured(
        GeneratedReport,
        (
            "Write an administrator report from the supplied SQLite context only. Keep every "
            "metric and student/task fact exactly consistent with the input. Do not claim trends "
            "unless timestamps show multiple comparable periods. Provide evidence-grounded "
            "insights and recommendations. Return only JSON matching the schema."
        ),
        {"report_type": report_type, "database_context": context},
    )
    return {
        "title": report.title,
        "report_type": report_type,
        "facts": context,
        "ai_analysis": report.model_dump(),
    }
