from __future__ import annotations

import json
import re
import sqlite3
from datetime import date
from typing import Any


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def dashboard_data(connection: sqlite3.Connection) -> dict[str, Any]:
    totals = connection.execute(
        """SELECT
               (SELECT COUNT(*) FROM students WHERE is_active = 1) AS total_students,
               (SELECT COUNT(*) FROM student_tasks WHERE status != 'Completed') AS active_tasks,
               (SELECT COUNT(*) FROM student_tasks WHERE status = 'Completed') AS completed_tasks,
               (SELECT COUNT(*) FROM student_tasks WHERE status = 'Pending') AS pending_tasks,
               (SELECT COUNT(*) FROM student_tasks WHERE status = 'In Progress') AS in_progress_tasks,
               (SELECT COUNT(*) FROM student_tasks
                 WHERE status != 'Completed' AND deadline < date('now', 'localtime')) AS overdue_tasks,
               (SELECT COUNT(*) FROM student_tasks) AS total_assignments,
               (SELECT AVG(performance_score) FROM student_tasks
                 WHERE performance_score IS NOT NULL) AS overall_performance"""
    ).fetchone()
    batch_rows = connection.execute(
        """SELECT s.batch, COUNT(DISTINCT s.id) AS student_count,
                  COUNT(st.id) AS assignment_count,
                  SUM(CASE WHEN st.status = 'Completed' THEN 1 ELSE 0 END) AS completed_count,
                  SUM(CASE WHEN st.status != 'Completed' AND st.deadline < date('now', 'localtime')
                      THEN 1 ELSE 0 END) AS overdue_count
           FROM students s LEFT JOIN student_tasks st ON st.student_id = s.id
           WHERE s.is_active = 1 GROUP BY s.batch ORDER BY s.batch"""
    ).fetchall()
    activities = connection.execute(
        """SELECT id, event_type, summary, created_at
           FROM activity_log ORDER BY created_at DESC, id DESC LIMIT 8"""
    ).fetchall()
    if not activities:
        activities = connection.execute(
            """SELECT st.id, 'assignment' AS event_type,
                      s.full_name || ' · ' || t.title || ' · ' || st.status AS summary,
                      st.assigned_at AS created_at
               FROM student_tasks st JOIN students s ON s.id = st.student_id
               JOIN tasks t ON t.id = st.task_id
               ORDER BY st.assigned_at DESC, st.id DESC LIMIT 8"""
        ).fetchall()
    assignment_count = int(totals["total_assignments"] or 0)
    complete_count = int(totals["completed_tasks"] or 0)
    return {
        "total_students": int(totals["total_students"] or 0),
        "active_tasks": int(totals["active_tasks"] or 0),
        "completed_tasks": complete_count,
        "completion_rate": round(complete_count * 100 / assignment_count, 1)
        if assignment_count
        else 0.0,
        "pending_tasks": int(totals["pending_tasks"] or 0),
        "in_progress_tasks": int(totals["in_progress_tasks"] or 0),
        "overdue_tasks": int(totals["overdue_tasks"] or 0),
        "overall_performance": round(float(totals["overall_performance"]), 1)
        if totals["overall_performance"] is not None
        else None,
        "batch_overview": [
            {
                **_row_dict(row),
                "completion_rate": round(
                    int(row["completed_count"] or 0) * 100 / int(row["assignment_count"]), 1
                )
                if row["assignment_count"]
                else 0.0,
            }
            for row in batch_rows
        ],
        "recent_activity": [_row_dict(row) for row in activities],
    }


def list_students(
    connection: sqlite3.Connection,
    search: str | None,
    course: str | None,
    batch: str | None,
    active: bool | None,
) -> list[dict[str, Any]]:
    clauses = ["1 = 1"]
    values: list[Any] = []
    if search:
        needle = f"%{search.strip()}%"
        clauses.append("(s.full_name LIKE ? OR s.student_id LIKE ? OR s.registration_number LIKE ?)")
        values.extend([needle, needle, needle])
    if course:
        clauses.append("s.course = ?")
        values.append(course)
    if batch:
        clauses.append("s.batch = ?")
        values.append(batch)
    if active is not None:
        clauses.append("s.is_active = ?")
        values.append(int(active))
    rows = connection.execute(
        f"""SELECT s.id, s.student_id, s.registration_number, s.full_name, s.email,
                   s.course, s.batch, s.current_level, s.is_active, s.created_at,
                   COUNT(st.id) AS total_tasks,
                   SUM(CASE WHEN st.status = 'Completed' THEN 1 ELSE 0 END) AS completed_tasks,
                   SUM(CASE WHEN st.status != 'Completed' AND st.deadline < date('now', 'localtime')
                       THEN 1 ELSE 0 END) AS overdue_tasks,
                   AVG(st.performance_score) AS performance_average,
                   SUM(CASE WHEN st.completed_at >= datetime('now', '-30 days')
                       THEN 1 ELSE 0 END) AS recent_completions,
                   SUM(CASE WHEN st.completed_at < datetime('now', '-30 days')
                       AND st.completed_at >= datetime('now', '-60 days')
                       THEN 1 ELSE 0 END) AS previous_period_completions
            FROM students s LEFT JOIN student_tasks st ON st.student_id = s.id
            WHERE {' AND '.join(clauses)}
            GROUP BY s.id ORDER BY s.full_name COLLATE NOCASE""",
        values,
    ).fetchall()
    return [_student_summary(row) for row in rows]


def student_filter_options(connection: sqlite3.Connection) -> dict[str, list[str]]:
    courses = connection.execute(
        "SELECT DISTINCT course FROM students ORDER BY course COLLATE NOCASE"
    ).fetchall()
    batches = connection.execute(
        "SELECT DISTINCT batch FROM students ORDER BY batch COLLATE NOCASE"
    ).fetchall()
    return {
        "courses": [row["course"] for row in courses],
        "batches": [row["batch"] for row in batches],
    }


def _student_summary(row: sqlite3.Row) -> dict[str, Any]:
    total = int(row["total_tasks"] or 0)
    completed = int(row["completed_tasks"] or 0)
    performance = row["performance_average"]
    return {
        "id": row["id"],
        "student_id": row["student_id"],
        "registration_number": row["registration_number"],
        "full_name": row["full_name"],
        "email": row["email"],
        "course": row["course"],
        "batch": row["batch"],
        "current_level": row["current_level"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
        "total_tasks": total,
        "completed_tasks": completed,
        "overdue_tasks": int(row["overdue_tasks"] or 0),
        "completion_percentage": round(100 * completed / total, 1) if total else 0.0,
        "performance_average": round(float(performance), 1) if performance is not None else None,
    }


def get_student_profile(connection: sqlite3.Connection, student_id: int) -> dict[str, Any] | None:
    student = connection.execute(
        """SELECT id, student_id, registration_number, full_name, email, course,
                  batch, current_level, is_active, created_at, updated_at
           FROM students WHERE id = ?""",
        (student_id,),
    ).fetchone()
    if student is None:
        return None
    tasks = connection.execute(
        """SELECT st.id AS assignment_id, t.id AS task_id, t.title, t.description,
                  t.topic, t.difficulty, st.status, st.deadline, st.performance_score,
                  st.assigned_at, st.completed_at
           FROM student_tasks st JOIN tasks t ON t.id = st.task_id
           WHERE st.student_id = ? ORDER BY st.deadline, t.title""",
        (student_id,),
    ).fetchall()
    skills = connection.execute(
        """SELECT topic, mastery_score, recorded_at FROM student_skills
           WHERE student_id = ? ORDER BY mastery_score DESC, topic""",
        (student_id,),
    ).fetchall()
    recent = connection.execute(
        """SELECT
               SUM(CASE WHEN completed_at >= datetime('now', '-30 days') THEN 1 ELSE 0 END)
                   AS recent_completions,
               SUM(CASE WHEN completed_at < datetime('now', '-30 days')
                   AND completed_at >= datetime('now', '-60 days') THEN 1 ELSE 0 END)
                   AS previous_completions
           FROM student_tasks WHERE student_id = ?""",
        (student_id,),
    ).fetchone()
    total = len(tasks)
    completed = sum(row["status"] == "Completed" for row in tasks)
    overdue = sum(
        row["status"] != "Completed" and row["deadline"] < date.today().isoformat()
        for row in tasks
    )
    scores = [row["performance_score"] for row in tasks if row["performance_score"] is not None]
    return {
        "student": {**_row_dict(student), "is_active": bool(student["is_active"])},
        "metrics": {
            "total_tasks": total,
            "completed_tasks": completed,
            "pending_tasks": sum(row["status"] == "Pending" for row in tasks),
            "in_progress_tasks": sum(row["status"] == "In Progress" for row in tasks),
            "overdue_tasks": overdue,
            "recent_completions_30d": int(recent["recent_completions"] or 0),
            "previous_completions_30d": int(recent["previous_completions"] or 0),
            "completion_percentage": round(100 * completed / total, 1) if total else 0.0,
            "performance_average": round(sum(scores) / len(scores), 1) if scores else None,
        },
        "tasks": [_row_dict(row) for row in tasks],
        "skills": [_row_dict(row) for row in skills],
    }


def insert_student(
    connection: sqlite3.Connection,
    *,
    registration_number: str,
    full_name: str,
    email: str | None,
    course: str,
    batch: str,
    current_level: str,
    password_hash: str,
) -> dict[str, Any]:
    code = course_code(course)
    existing = connection.execute(
        "SELECT student_id FROM students WHERE student_id LIKE ?", (f"SKX-{code}-%",)
    ).fetchall()
    suffix = max(
        (int(match.group(1)) for row in existing
         if (match := re.fullmatch(rf"SKX-{re.escape(code)}-(\d+)", row["student_id"]))),
        default=0,
    ) + 1
    while True:
        student_id = f"SKX-{code}-{suffix:04d}"
        exists = connection.execute(
            "SELECT 1 FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        if exists is None:
            break
        suffix += 1
    cursor = connection.execute(
        """INSERT INTO students
           (student_id, registration_number, full_name, email, course, batch, current_level, password_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            student_id,
            registration_number,
            full_name,
            email,
            course,
            batch,
            current_level,
            password_hash,
        ),
    )
    connection.execute(
        "INSERT INTO activity_log (event_type, summary) VALUES ('student_created', ?)",
        (f"Student created · {full_name} · {student_id}",),
    )
    profile = get_student_profile(connection, int(cursor.lastrowid))
    assert profile is not None
    return profile["student"]


def course_code(course: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9 ]", " ", course).split()
    known = {
        "data analytics": "DA",
        "python development": "PY",
        "web development": "WD",
    }
    return known.get(course.casefold(), "".join(word[0] for word in normalized[:2]).upper() or "ST")


def update_student(
    connection: sqlite3.Connection, student_id: int, changes: dict[str, Any]
) -> dict[str, Any] | None:
    if not changes:
        return get_student_profile(connection, student_id)
    allowed = {"full_name", "email", "course", "batch", "current_level"}
    changes = {key: value for key, value in changes.items() if key in allowed}
    assignments = ", ".join(f"{key} = ?" for key in changes)
    cursor = connection.execute(
        f"UPDATE students SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        [*changes.values(), student_id],
    )
    if cursor.rowcount == 0:
        return None
    student = connection.execute(
        "SELECT full_name, student_id FROM students WHERE id = ?", (student_id,)
    ).fetchone()
    connection.execute(
        "INSERT INTO activity_log (event_type, summary) VALUES ('student_updated', ?)",
        (f"Student profile updated · {student['full_name']} · {student['student_id']}",),
    )
    return get_student_profile(connection, student_id)


def set_student_active(
    connection: sqlite3.Connection, student_id: int, active: bool
) -> bool:
    student = connection.execute(
        "SELECT full_name, student_id FROM students WHERE id = ?", (student_id,)
    ).fetchone()
    if student is None:
        return False
    connection.execute(
        "UPDATE students SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (int(active), student_id),
    )
    if not active:
        connection.execute(
            """UPDATE sessions SET revoked_at = CURRENT_TIMESTAMP
               WHERE user_id = ? AND role = 'student' AND revoked_at IS NULL""",
            (student_id,),
        )
    event = "student_activated" if active else "student_deactivated"
    connection.execute(
        "INSERT INTO activity_log (event_type, summary) VALUES (?, ?)",
        (event, f"Student {'activated' if active else 'deactivated'} · {student['full_name']}"),
    )
    return True


def delete_student(connection: sqlite3.Connection, student_id: int) -> bool:
    student = connection.execute(
        "SELECT full_name FROM students WHERE id = ?", (student_id,)
    ).fetchone()
    if student is None:
        return False
    connection.execute(
        "INSERT INTO activity_log (event_type, summary) VALUES ('student_deleted', ?)",
        (f"Student deleted · {student['full_name']}",),
    )
    connection.execute(
        """UPDATE sessions SET revoked_at = CURRENT_TIMESTAMP
           WHERE user_id = ? AND role = 'student' AND revoked_at IS NULL""",
        (student_id,),
    )
    connection.execute("DELETE FROM students WHERE id = ?", (student_id,))
    return True


def list_tasks(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """SELECT t.id, t.title, t.description, t.topic, t.course, t.difficulty,
                  t.priority, t.estimated_minutes, t.requirements_json, t.expected_outcome,
                  t.evaluation_criteria_json, t.created_at,
                  COUNT(st.id) AS assigned_count
           FROM tasks t LEFT JOIN student_tasks st ON st.task_id = t.id
           GROUP BY t.id ORDER BY t.created_at DESC, t.id DESC"""
    ).fetchall()
    return [
        {
            **{
                key: row[key]
                for key in (
                    "id", "title", "description", "topic", "course", "difficulty",
                    "priority", "estimated_minutes", "expected_outcome", "created_at",
                    "assigned_count",
                )
            },
            "requirements": json.loads(row["requirements_json"]),
            "evaluation_criteria": json.loads(row["evaluation_criteria_json"]),
        }
        for row in rows
    ]


def insert_task(
    connection: sqlite3.Connection,
    task: dict[str, Any],
) -> dict[str, Any]:
    cursor = connection.execute(
        """INSERT INTO tasks
           (title, description, topic, course, difficulty, priority, estimated_minutes,
            requirements_json, expected_outcome, evaluation_criteria_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            task["title"],
            task["description"],
            task["topic"],
            task["course"],
            task["difficulty"],
            task["priority"],
            task["estimated_minutes"],
            json.dumps(task["requirements"]),
            task["expected_outcome"],
            json.dumps(task["evaluation_criteria"]),
        ),
    )
    connection.execute(
        "INSERT INTO activity_log (event_type, summary) VALUES ('task_created', ?)",
        (f"Task created · {task['title']}",),
    )
    return next(item for item in list_tasks(connection) if item["id"] == cursor.lastrowid)


def assign_task(
    connection: sqlite3.Connection,
    task_id: int,
    student_ids: list[int],
    deadline: str,
) -> int:
    task = connection.execute(
        "SELECT id, title, course FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()
    if task is None:
        raise LookupError("Task not found.")
    unique_ids = list(dict.fromkeys(student_ids))
    placeholders = ",".join("?" for _ in unique_ids)
    students = connection.execute(
        f"SELECT id, full_name, student_id, course FROM students WHERE id IN ({placeholders}) AND is_active = 1",
        unique_ids,
    ).fetchall()
    if len(students) != len(unique_ids):
        raise ValueError("One or more selected students are missing or inactive.")
    wrong_course = [student["student_id"] for student in students if student["course"] != task["course"]]
    if wrong_course:
        raise ValueError("Task can only be assigned to students in the task's course.")
    existing = {
        row["student_id"]
        for row in connection.execute(
            f"SELECT student_id FROM student_tasks WHERE task_id = ? AND student_id IN ({placeholders})",
            [task_id, *unique_ids],
        )
    }
    if existing:
        raise ValueError("The task is already assigned to one or more selected students.")
    connection.executemany(
        """INSERT INTO student_tasks (student_id, task_id, deadline)
           VALUES (?, ?, ?)""",
        [(student_id, task_id, deadline) for student_id in unique_ids],
    )
    for student in students:
        connection.execute(
            "INSERT INTO activity_log (event_type, summary) VALUES ('task_assigned', ?)",
            (f"Task assigned · {task['title']} → {student['full_name']}",),
        )
    return len(students)


def task_candidates(
    connection: sqlite3.Connection, course: str, level: str, topic: str
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """SELECT s.id, s.student_id, s.full_name, s.course, s.current_level,
                  COUNT(st.id) AS assigned_tasks,
                  SUM(CASE WHEN st.status = 'Completed' THEN 1 ELSE 0 END) AS completed_tasks,
                  AVG(st.performance_score) AS performance_average,
                  ss.mastery_score AS topic_mastery
           FROM students s LEFT JOIN student_tasks st ON st.student_id = s.id
           LEFT JOIN student_skills ss ON ss.student_id = s.id AND ss.topic = ?
           WHERE s.is_active = 1 AND s.course = ?
           GROUP BY s.id ORDER BY s.full_name""",
        (topic, course),
    ).fetchall()
    candidates = []
    for row in rows:
        if row["current_level"] != level:
            continue
        assigned = int(row["assigned_tasks"] or 0)
        completed = int(row["completed_tasks"] or 0)
        score = row["performance_average"]
        candidates.append(
            {
                "id": row["id"],
                "student_id": row["student_id"],
                "full_name": row["full_name"],
                "course": row["course"],
                "current_level": row["current_level"],
                "assigned_tasks": assigned,
                "completed_tasks": completed,
                "completion_percentage": round(100 * completed / assigned, 1) if assigned else 0.0,
                "performance_average": round(float(score), 1) if score is not None else None,
                "topic_mastery": row["topic_mastery"],
            }
        )
    return candidates


def performance_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    students = connection.execute(
        """SELECT s.id, s.student_id, s.full_name, s.course, s.batch, s.current_level,
                  COUNT(st.id) AS total_tasks,
                  SUM(CASE WHEN st.status = 'Completed' THEN 1 ELSE 0 END) AS completed_tasks,
                  SUM(CASE WHEN st.status = 'Pending' THEN 1 ELSE 0 END) AS pending_tasks,
                  SUM(CASE WHEN st.status = 'In Progress' THEN 1 ELSE 0 END) AS in_progress_tasks,
                  SUM(CASE WHEN st.status != 'Completed' AND st.deadline < date('now', 'localtime')
                      THEN 1 ELSE 0 END) AS overdue_tasks,
                  AVG(st.performance_score) AS performance_average,
                  SUM(CASE WHEN st.completed_at >= datetime('now', '-30 days')
                      THEN 1 ELSE 0 END) AS recent_completions,
                  SUM(CASE WHEN st.completed_at < datetime('now', '-30 days')
                      AND st.completed_at >= datetime('now', '-60 days')
                      THEN 1 ELSE 0 END) AS previous_period_completions
           FROM students s LEFT JOIN student_tasks st ON st.student_id = s.id
           WHERE s.is_active = 1 GROUP BY s.id ORDER BY s.full_name"""
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in students:
        total = int(row["total_tasks"] or 0)
        completed = int(row["completed_tasks"] or 0)
        pending = int(row["pending_tasks"] or 0)
        in_progress = int(row["in_progress_tasks"] or 0)
        overdue = int(row["overdue_tasks"] or 0)
        recent = int(row["recent_completions"] or 0)
        previous = int(row["previous_period_completions"] or 0)
        completion = round(100 * completed / total, 1) if total else 0.0
        if overdue >= 2 or (overdue > 0 and completion < 50):
            risk = "AT RISK"
        elif overdue or completion < 60 or total == 0:
            risk = "NEEDS ATTENTION"
        else:
            risk = "ON TRACK"
        reasons = []
        if overdue:
            reasons.append(f"{overdue} task(s) are past deadline.")
        if total and completion < 60:
            reasons.append(f"Completion is {completion}%.")
        if total == 0:
            reasons.append("No tasks have been assigned yet.")
        if not reasons:
            reasons.append("No overdue tasks and completion is at least 60%.")
        if overdue:
            action = "Prioritize the past-deadline task(s) and agree on a realistic completion plan."
        elif total == 0:
            action = "Assign a first task matched to the student's course and current level."
        elif completion < 60:
            action = "Review the pending workload and schedule a focused progress check-in."
        else:
            action = "Continue the current learning plan and acknowledge progress."
        result.append(
            {
                "id": row["id"],
                "student_id": row["student_id"],
                "full_name": row["full_name"],
                "course": row["course"],
                "batch": row["batch"],
                "current_level": row["current_level"],
                "classification": risk,
                "metrics": {
                    "total_tasks": total,
                    "completed_tasks": completed,
                    "pending_tasks": pending,
                    "in_progress_tasks": in_progress,
                    "overdue_tasks": overdue,
                    "completion_percentage": completion,
                    "recent_completions_30d": recent,
                    "previous_completions_30d": previous,
                    "completion_trend": "up"
                    if recent > previous
                    else "down"
                    if recent < previous
                    else "steady",
                    "performance_average": round(float(row["performance_average"]), 1)
                    if row["performance_average"] is not None
                    else None,
                },
                "reasons": reasons,
                "suggested_action": action,
            }
        )
    return result


def batch_names(connection: sqlite3.Connection) -> list[str]:
    return [
        row["batch"]
        for row in connection.execute(
            "SELECT DISTINCT batch FROM students WHERE is_active = 1 ORDER BY batch"
        )
    ]


def batch_data(connection: sqlite3.Connection, batch: str) -> dict[str, Any] | None:
    students = list_students(connection, None, None, batch, True)
    if not students:
        return None
    ids = [student["id"] for student in students]
    placeholders = ",".join("?" for _ in ids)
    assignments = connection.execute(
        f"""SELECT st.id, st.status, st.deadline, st.performance_score,
                    t.topic, t.difficulty, s.full_name, s.student_id
             FROM student_tasks st JOIN tasks t ON t.id = st.task_id
             JOIN students s ON s.id = st.student_id
             WHERE st.student_id IN ({placeholders})""",
        ids,
    ).fetchall()
    total = len(assignments)
    completed = sum(row["status"] == "Completed" for row in assignments)
    scores = [row["performance_score"] for row in assignments if row["performance_score"] is not None]
    topic_rows = connection.execute(
        f"""SELECT ss.topic, AVG(ss.mastery_score) AS average_mastery,
                   COUNT(DISTINCT ss.student_id) AS student_count
            FROM student_skills ss WHERE ss.student_id IN ({placeholders})
            GROUP BY ss.topic ORDER BY average_mastery DESC""",
        ids,
    ).fetchall()
    difficulty_counts = connection.execute(
        f"""SELECT t.difficulty, COUNT(*) AS assignments,
                   SUM(CASE WHEN st.status = 'Completed' THEN 1 ELSE 0 END) AS completed,
                   AVG(st.performance_score) AS average_performance
            FROM student_tasks st JOIN tasks t ON t.id = st.task_id
            WHERE st.student_id IN ({placeholders}) GROUP BY t.difficulty ORDER BY t.difficulty""",
        ids,
    ).fetchall()
    risks = [row for row in performance_rows(connection) if row["batch"] == batch]
    period = connection.execute(
        f"""SELECT strftime('%Y-%W', st.assigned_at) AS week,
                   COUNT(*) AS assigned,
                   SUM(CASE WHEN st.status = 'Completed' THEN 1 ELSE 0 END) AS completed
            FROM student_tasks st WHERE st.student_id IN ({placeholders})
            GROUP BY week ORDER BY week DESC LIMIT 8""",
        ids,
    ).fetchall()
    return {
        "batch": batch,
        "student_count": len(students),
        "average_completion": round(
            sum(student["completion_percentage"] for student in students) / len(students), 1
        ),
        "average_performance": round(sum(scores) / len(scores), 1) if scores else None,
        "pending_tasks": sum(row["status"] == "Pending" for row in assignments),
        "overdue_tasks": sum(
            row["status"] != "Completed" and row["deadline"] < date.today().isoformat()
            for row in assignments
        ),
        "completion_rate": round(100 * completed / total, 1) if total else 0.0,
        "strong_topics": [
            _row_dict(row) for row in topic_rows if row["average_mastery"] >= 80
        ],
        "weak_topics": [
            _row_dict(row)
            for row in reversed(topic_rows)
            if row["average_mastery"] < 65
        ],
        "topic_mastery": [_row_dict(row) for row in topic_rows],
        "difficulty_patterns": [
            {
                **_row_dict(row),
                "average_performance": round(float(row["average_performance"]), 1)
                if row["average_performance"] is not None
                else None,
            }
            for row in difficulty_counts
        ],
        "students_needing_support": [
            {
                "id": row["id"],
                "student_id": row["student_id"],
                "full_name": row["full_name"],
                "classification": row["classification"],
                "metrics": row["metrics"],
            }
            for row in risks
            if row["classification"] != "ON TRACK"
        ],
        "weekly_trend": [_row_dict(row) for row in period],
        "students": students,
    }


def copilot_context(connection: sqlite3.Connection, intent: str) -> dict[str, Any]:
    if intent == "overdue":
        rows = connection.execute(
            """SELECT s.student_id, s.full_name, s.course, s.batch, t.title,
                      st.deadline, st.status
               FROM student_tasks st JOIN students s ON s.id = st.student_id
               JOIN tasks t ON t.id = st.task_id
               WHERE s.is_active = 1 AND st.status != 'Completed'
                 AND st.deadline < date('now', 'localtime')
               ORDER BY st.deadline, s.full_name"""
        ).fetchall()
    elif intent == "highest_performance":
        rows = connection.execute(
            """SELECT s.student_id, s.full_name, s.course, s.batch,
                      ROUND(AVG(st.performance_score), 1) AS average_performance,
                      COUNT(st.id) AS scored_tasks
               FROM students s JOIN student_tasks st ON st.student_id = s.id
               WHERE s.is_active = 1 AND st.performance_score IS NOT NULL
               GROUP BY s.id ORDER BY average_performance DESC, s.full_name LIMIT 10"""
        ).fetchall()
    elif intent == "needs_attention":
        rows = [
            {
                "student_id": row["student_id"],
                "full_name": row["full_name"],
                "batch": row["batch"],
                "classification": row["classification"],
                "metrics": row["metrics"],
                "reasons": row["reasons"],
            }
            for row in performance_rows(connection)
            if row["classification"] != "ON TRACK"
        ]
    elif intent == "pending":
        rows = connection.execute(
            """SELECT s.student_id, s.full_name, s.batch, COUNT(*) AS pending_tasks
               FROM student_tasks st JOIN students s ON s.id = st.student_id
               WHERE s.is_active = 1 AND st.status = 'Pending'
               GROUP BY s.id ORDER BY pending_tasks DESC, s.full_name"""
        ).fetchall()
    elif intent == "weekly":
        rows = connection.execute(
            """SELECT COUNT(*) AS assignments,
                      SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completed,
                      SUM(CASE WHEN status != 'Completed' AND deadline < date('now', 'localtime')
                          THEN 1 ELSE 0 END) AS overdue,
                      AVG(performance_score) AS average_performance
               FROM student_tasks
               WHERE assigned_at >= datetime('now', '-7 days')"""
        ).fetchone()
        rows = _row_dict(rows)
    elif intent == "best_batch":
        batch_list = batch_names(connection)
        rows = []
        for name in batch_list:
            data = batch_data(connection, name)
            if data:
                rows.append(
                    {
                        "batch": name,
                        "average_completion": data["average_completion"],
                        "average_performance": data["average_performance"],
                        "student_count": data["student_count"],
                    }
                )
        rows.sort(
            key=lambda row: (
                row["average_performance"] if row["average_performance"] is not None else -1,
                row["average_completion"],
            ),
            reverse=True,
        )
    else:
        raise ValueError("Unsupported question.")
    return {"intent": intent, "records": rows}


def report_context(
    connection: sqlite3.Connection,
    report_type: str,
    student_id: int | None,
    batch: str | None,
) -> tuple[dict[str, Any], int | None]:
    if report_type == "student":
        if student_id is None:
            raise ValueError("student_id is required for a student report.")
        profile = get_student_profile(connection, student_id)
        if profile is None:
            raise LookupError("Student not found.")
        context = {
            "student": {
                key: profile["student"][key]
                for key in ("student_id", "course", "batch", "current_level")
            },
            "metrics": profile["metrics"],
            "tasks": profile["tasks"],
            "recorded_topic_mastery": profile["skills"],
        }
        return context, student_id
    if report_type == "batch":
        if batch is None:
            raise ValueError("batch is required for a batch report.")
        data = batch_data(connection, batch)
        if data is None:
            raise LookupError("Batch not found.")
        return data, None
    if report_type == "performance":
        return {"students": performance_rows(connection)}, None
    weekly = copilot_context(connection, "weekly")
    weekly["recent_completions"] = [
        _row_dict(row)
        for row in connection.execute(
            """SELECT s.student_id, s.full_name, t.title, st.completed_at
               FROM student_tasks st JOIN students s ON s.id = st.student_id
               JOIN tasks t ON t.id = st.task_id
               WHERE st.status = 'Completed' AND st.completed_at >= datetime('now', '-7 days')
               ORDER BY st.completed_at DESC LIMIT 100"""
        )
    ]
    return weekly, None


def store_report(
    connection: sqlite3.Connection,
    student_id: int | None,
    report_type: str,
    content: dict[str, Any],
) -> dict[str, Any]:
    cursor = connection.execute(
        "INSERT INTO reports (student_id, report_type, content_json) VALUES (?, ?, ?)",
        (student_id, report_type, json.dumps(content)),
    )
    connection.execute(
        "INSERT INTO activity_log (event_type, summary) VALUES ('report_generated', ?)",
        (f"{report_type.title()} report generated · {content['title']}",),
    )
    row = connection.execute(
        "SELECT id, student_id, report_type, created_at FROM reports WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return {**_row_dict(row), "content": content}


def list_reports(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """SELECT r.id, r.student_id, s.student_id AS student_code, s.full_name,
                  r.report_type, r.content_json, r.created_at
           FROM reports r LEFT JOIN students s ON s.id = r.student_id
           ORDER BY r.created_at DESC, r.id DESC LIMIT 100"""
    ).fetchall()
    return [
        {
            **{key: row[key] for key in (
                "id", "student_id", "student_code", "full_name", "report_type", "created_at"
            )},
            "content": json.loads(row["content_json"]),
        }
        for row in rows
    ]
