from __future__ import annotations

from pathlib import Path

from .database import database_session
from .security import generate_initial_password, hash_password, verify_password

DEMO_STUDENTS = (
    ("SKX-DA-0001", "REG-DA-0001", "Arjun Kumar", "Data Analytics", "DA-2026-A", "Beginner"),
    ("SKX-PY-0002", "REG-PY-0002", "Priya Sharma", "Python Development", "PY-2026-A", "Intermediate"),
    ("SKX-WD-0003", "REG-WD-0003", "Rahul Verma", "Web Development", "WD-2026-A", "Beginner"),
    ("SKX-DA-0004", "REG-DA-0004", "Sneha Reddy", "Data Analytics", "DA-2026-B", "Advanced"),
    ("SKX-PY-0005", "REG-PY-0005", "Kiran Kumar", "Python Development", "PY-2026-B", "Intermediate"),
)

DEMO_TASKS = (
    ("Explore a dataset", "Inspect a small dataset and document its columns and quality.", "Data exploration", "Data Analytics", "Beginner", "Normal", 60),
    ("Build a reusable Python function", "Write and test a function that validates structured input.", "Functions", "Python Development", "Intermediate", "High", 90),
    ("Create an accessible page", "Build a responsive page using semantic HTML and CSS.", "Frontend foundations", "Web Development", "Beginner", "Normal", 120),
    ("Summarize a data trend", "Use a chart and a short written summary to communicate a trend.", "Data visualization", "Data Analytics", "Intermediate", "High", 90),
    ("Test a REST endpoint", "Write focused tests for success and validation cases.", "API testing", "Python Development", "Advanced", "Normal", 75),
)

ASSIGNMENTS = (
    (0, 0, "Completed", "2026-12-01", 62.0),
    (0, 3, "In Progress", "2026-09-30", None),
    (1, 1, "Completed", "2026-12-02", 94.0),
    (1, 4, "Pending", "2026-12-12", None),
    (2, 2, "In Progress", "2026-09-28", None),
    (2, 1, "Pending", "2026-12-15", None),
    (3, 0, "Completed", "2026-12-01", 91.0),
    (3, 3, "Completed", "2026-12-05", 88.0),
    (4, 1, "In Progress", "2026-12-09", None),
    (4, 4, "Pending", "2026-12-16", None),
)

DEMO_SKILLS = (
    (0, "Data exploration", 54.0),
    (0, "Data visualization", 62.0),
    (1, "Functions", 91.0),
    (1, "API testing", 72.0),
    (2, "Frontend foundations", 67.0),
    (2, "Functions", 58.0),
    (3, "Data exploration", 93.0),
    (3, "Data visualization", 88.0),
    (4, "Functions", 76.0),
    (4, "API testing", 69.0),
)


def seed_demo_data(database_path: Path) -> None:
    with database_session(database_path) as connection:
        fixture_credentials_migrated = (
            connection.execute("SELECT COUNT(*) FROM student_skills").fetchone()[0]
            >= len(DEMO_SKILLS)
        )
        for student in DEMO_STUDENTS:
            exists = connection.execute(
                "SELECT password_hash FROM students WHERE student_id = ?", (student[0],)
            ).fetchone()
            if exists is None:
                connection.execute(
                    """INSERT INTO students
                       (student_id, registration_number, full_name, course, batch, current_level, password_hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        *student,
                        hash_password(generate_initial_password(student[2], student[1])),
                    ),
                )
            elif not fixture_credentials_migrated and not verify_password(
                exists["password_hash"], generate_initial_password(student[2], student[1])
            ):
                connection.execute(
                    "UPDATE students SET password_hash = ? WHERE student_id = ?",
                    (
                        hash_password(generate_initial_password(student[2], student[1])),
                        student[0],
                    ),
                )
        for task in DEMO_TASKS:
            connection.execute(
                """INSERT OR IGNORE INTO tasks
                   (title, description, topic, course, difficulty, priority, estimated_minutes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                task,
            )
        student_ids = {
            row["student_id"]: row["id"]
            for row in connection.execute("SELECT id, student_id FROM students")
        }
        task_ids = {
            row["title"]: row["id"]
            for row in connection.execute("SELECT id, title FROM tasks")
        }
        student_keys = [student[0] for student in DEMO_STUDENTS]
        task_titles = [task[0] for task in DEMO_TASKS]
        for student_index, task_index, task_status, deadline, score in ASSIGNMENTS:
            assignment_values = (
                student_ids[student_keys[student_index]],
                task_ids[task_titles[task_index]],
                task_status,
                deadline,
                score,
            )
            connection.execute(
                """INSERT OR IGNORE INTO student_tasks
                   (student_id, task_id, status, deadline, performance_score, completed_at)
                   VALUES (?, ?, ?, ?, ?, CASE WHEN ? = 'Completed' THEN CURRENT_TIMESTAMP END)""",
                (*assignment_values, task_status),
            )
            if task_status == "Completed":
                connection.execute(
                    """UPDATE student_tasks SET completed_at = CURRENT_TIMESTAMP
                       WHERE student_id = ? AND task_id = ? AND completed_at IS NULL""",
                    assignment_values[:2],
                )
        for student_index, topic, mastery_score in DEMO_SKILLS:
            connection.execute(
                """INSERT OR IGNORE INTO student_skills
                   (student_id, topic, mastery_score) VALUES (?, ?, ?)""",
                (student_ids[student_keys[student_index]], topic, mastery_score),
            )
