from __future__ import annotations

import json
import sqlite3
from datetime import date
from typing import Any


TASK_SELECT = """SELECT st.id AS assignment_id, t.title, t.description, t.topic,
                        t.course, t.difficulty, t.priority, t.estimated_minutes,
                        st.status, st.deadline, st.performance_score, st.assigned_at,
                        st.completed_at
                 FROM student_tasks st
                 JOIN tasks t ON t.id = st.task_id"""


def student_tasks(connection: sqlite3.Connection, student_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        f"""{TASK_SELECT}
            WHERE st.student_id = ?
            ORDER BY CASE WHEN st.status = 'Completed' THEN 2
                          WHEN st.deadline < date('now', 'localtime') THEN 0
                          ELSE 1 END,
                     st.deadline,
                     CASE t.priority WHEN 'High' THEN 0 WHEN 'Normal' THEN 1 ELSE 2 END,
                     st.id""",
        (student_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def student_dashboard(
    connection: sqlite3.Connection, student_id: int
) -> dict[str, Any] | None:
    student = connection.execute(
        """SELECT id, student_id, full_name, course, batch, current_level
           FROM students WHERE id = ? AND is_active = 1""",
        (student_id,),
    ).fetchone()
    if student is None:
        return None

    tasks = student_tasks(connection, student_id)
    total = len(tasks)
    completed = sum(task["status"] == "Completed" for task in tasks)
    pending = sum(task["status"] == "Pending" for task in tasks)
    in_progress = sum(task["status"] == "In Progress" for task in tasks)
    today = date.today()
    actionable = [task for task in tasks if task["status"] != "Completed"]

    def priority_key(task: dict[str, Any]) -> tuple[int, int, int, int, int]:
        deadline = date.fromisoformat(task["deadline"])
        days_remaining = (deadline - today).days
        priority_rank = {"High": 0, "Normal": 1, "Low": 2}[task["priority"]]
        status_rank = {"In Progress": 0, "Pending": 1}[task["status"]]
        return (
            0 if days_remaining < 0 else 1,
            days_remaining,
            priority_rank,
            status_rank,
            int(task["assignment_id"]),
        )

    actionable.sort(key=priority_key)
    today_priority = None
    if actionable:
        selected = actionable[0]
        days_remaining = (date.fromisoformat(selected["deadline"]) - today).days
        if days_remaining < 0:
            reason = "This task is overdue."
        elif days_remaining == 0:
            reason = "This task is due today."
        elif days_remaining <= 3:
            reason = "This task is due within three days."
        elif selected["priority"] == "High":
            reason = "This task has high priority."
        else:
            reason = "This is the nearest outstanding deadline."
        today_priority = {**selected, "reason": reason}

    upcoming = [
        task
        for task in tasks
        if task["status"] != "Completed"
        and date.fromisoformat(task["deadline"]) >= today
    ][:5]
    return {
        "student": {key: student[key] for key in (
            "id", "student_id", "full_name", "course", "batch", "current_level"
        )},
        "total_tasks": total,
        "completed_tasks": completed,
        "pending_tasks": pending,
        "in_progress_tasks": in_progress,
        "overdue_tasks": sum(
            task["status"] != "Completed"
            and date.fromisoformat(task["deadline"]) < today
            for task in tasks
        ),
        "completion_percentage": round(completed * 100 / total, 1) if total else 0.0,
        "today_priority": today_priority,
        "upcoming_deadlines": upcoming,
        "tasks": tasks,
    }


def student_learning_records(
    connection: sqlite3.Connection, student_id: int
) -> dict[str, Any] | None:
    student = connection.execute(
        """SELECT id, student_id, full_name, course, batch, current_level
           FROM students WHERE id = ? AND is_active = 1""",
        (student_id,),
    ).fetchone()
    if student is None:
        return None

    recent_completions = connection.execute(
        f"""{TASK_SELECT}
            WHERE st.student_id = ? AND st.status = 'Completed'
            ORDER BY st.completed_at DESC, st.id DESC LIMIT 8""",
        (student_id,),
    ).fetchall()
    skills = connection.execute(
        """SELECT topic, mastery_score, recorded_at FROM student_skills
           WHERE student_id = ? ORDER BY mastery_score ASC, topic""",
        (student_id,),
    ).fetchall()
    recent_activity = connection.execute(
        """SELECT
             SUM(CASE WHEN assigned_at >= datetime('now', '-30 days') THEN 1 ELSE 0 END)
                 AS recent_assignments,
             SUM(CASE WHEN completed_at >= datetime('now', '-30 days') THEN 1 ELSE 0 END)
                 AS recent_completions
           FROM student_tasks WHERE student_id = ?""",
        (student_id,),
    ).fetchone()
    return {
        "student": dict(student),
        "tasks": student_tasks(connection, student_id),
        "skills": [dict(skill) for skill in skills],
        "recent_completions": [dict(task) for task in recent_completions],
        "recent_activity": {
            "assignments_last_30_days": int(recent_activity["recent_assignments"] or 0),
            "completions_last_30_days": int(recent_activity["recent_completions"] or 0),
        },
    }


def create_practice_session(
    connection: sqlite3.Connection,
    session_id: str,
    student_id: int,
    topic: str,
    practice_type: str,
    questions: list[dict[str, Any]],
) -> None:
    connection.execute(
        """DELETE FROM student_practice_sessions
           WHERE student_id = ? AND expires_at <= CURRENT_TIMESTAMP""",
        (student_id,),
    )
    connection.execute(
        """INSERT INTO student_practice_sessions
           (id, student_id, topic, practice_type, questions_json, expires_at)
           VALUES (?, ?, ?, ?, ?, datetime('now', '+2 hours'))""",
        (session_id, student_id, topic, practice_type, json.dumps(questions)),
    )


def consume_practice_session(
    connection: sqlite3.Connection, session_id: str, student_id: int
) -> dict[str, Any] | None:
    cursor = connection.execute(
        """UPDATE student_practice_sessions SET submitted_at = CURRENT_TIMESTAMP
           WHERE id = ? AND student_id = ? AND submitted_at IS NULL
             AND expires_at > CURRENT_TIMESTAMP""",
        (session_id, student_id),
    )
    if cursor.rowcount != 1:
        return None
    row = connection.execute(
        """SELECT id, topic, practice_type, questions_json
           FROM student_practice_sessions WHERE id = ? AND student_id = ?""",
        (session_id, student_id),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "topic": row["topic"],
        "practice_type": row["practice_type"],
        "questions": json.loads(row["questions_json"]),
    }


def delete_practice_session(
    connection: sqlite3.Connection, session_id: str, student_id: int
) -> None:
    connection.execute(
        "DELETE FROM student_practice_sessions WHERE id = ? AND student_id = ?",
        (session_id, student_id),
    )


def store_student_report(
    connection: sqlite3.Connection, student_id: int, report: dict[str, Any]
) -> dict[str, Any] | None:
    student = connection.execute(
        "SELECT id FROM students WHERE id = ? AND is_active = 1", (student_id,)
    ).fetchone()
    if student is None:
        return None
    cursor = connection.execute(
        """INSERT INTO reports (student_id, report_type, content_json)
           VALUES (?, 'student_progress', ?)""",
        (student_id, json.dumps(report, ensure_ascii=True)),
    )
    row = connection.execute(
        """SELECT id, report_type, created_at FROM reports
           WHERE id = ? AND student_id = ?""",
        (cursor.lastrowid, student_id),
    ).fetchone()
    return {**dict(row), "content": report}


def student_reports(
    connection: sqlite3.Connection, student_id: int
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """SELECT id, report_type, content_json, created_at FROM reports
           WHERE student_id = ? AND report_type = 'student_progress'
           ORDER BY created_at DESC, id DESC LIMIT 20""",
        (student_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "report_type": row["report_type"],
            "created_at": row["created_at"],
            "content": json.loads(row["content_json"]),
        }
        for row in rows
    ]


def update_student_task_status(
    connection: sqlite3.Connection,
    student_id: int,
    assignment_id: int,
    target_status: str,
) -> dict[str, Any] | None:
    assignment = connection.execute(
        "SELECT status FROM student_tasks WHERE id = ? AND student_id = ?",
        (assignment_id, student_id),
    ).fetchone()
    if assignment is None:
        return None

    next_status = {
        "Pending": "In Progress",
        "In Progress": "Completed",
    }.get(assignment["status"])
    if target_status != next_status:
        raise ValueError("Task status can only move from Pending to In Progress to Completed.")

    cursor = connection.execute(
        """UPDATE student_tasks
           SET status = ?, completed_at = CASE WHEN ? = 'Completed'
               THEN CURRENT_TIMESTAMP ELSE NULL END
           WHERE id = ? AND student_id = ? AND status = ?""",
        (
            target_status,
            target_status,
            assignment_id,
            student_id,
            assignment["status"],
        ),
    )
    if cursor.rowcount != 1:
        raise ValueError("Task status changed before the update could be saved.")
    return next(
        task for task in student_tasks(connection, student_id)
        if task["assignment_id"] == assignment_id
    )
