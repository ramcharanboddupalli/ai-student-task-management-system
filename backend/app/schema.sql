CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'student')),
    expires_at INTEGER NOT NULL,
    revoked_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY,
    student_id TEXT NOT NULL UNIQUE,
    registration_number TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE COLLATE NOCASE,
    course TEXT NOT NULL,
    batch TEXT NOT NULL,
    current_level TEXT NOT NULL DEFAULT 'Beginner',
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    topic TEXT NOT NULL,
    course TEXT NOT NULL,
    difficulty TEXT NOT NULL CHECK (difficulty IN ('Beginner', 'Intermediate', 'Advanced')),
    priority TEXT NOT NULL DEFAULT 'Normal' CHECK (priority IN ('Low', 'Normal', 'High')),
    estimated_minutes INTEGER NOT NULL CHECK (estimated_minutes > 0),
    requirements_json TEXT NOT NULL DEFAULT '[]',
    expected_outcome TEXT NOT NULL DEFAULT '',
    evaluation_criteria_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (title, course)
);

CREATE TABLE IF NOT EXISTS student_tasks (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'Pending'
        CHECK (status IN ('Pending', 'In Progress', 'Completed')),
    deadline TEXT NOT NULL,
    performance_score REAL CHECK (
        performance_score IS NULL OR (performance_score >= 0 AND performance_score <= 100)
    ),
    assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    UNIQUE (student_id, task_id)
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY,
    student_id INTEGER REFERENCES students(id) ON DELETE SET NULL,
    report_type TEXT NOT NULL,
    content_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_interactions (
    id INTEGER PRIMARY KEY,
    admin_id INTEGER REFERENCES admins(id) ON DELETE SET NULL,
    student_id INTEGER REFERENCES students(id) ON DELETE SET NULL,
    feature TEXT NOT NULL,
    prompt_summary TEXT NOT NULL,
    response_json TEXT,
    status TEXT NOT NULL CHECK (status IN ('succeeded', 'failed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS student_skills (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    mastery_score REAL NOT NULL CHECK (mastery_score >= 0 AND mastery_score <= 100),
    recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (student_id, topic)
);

CREATE TABLE IF NOT EXISTS student_practice_sessions (
    id TEXT PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    practice_type TEXT NOT NULL,
    questions_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL,
    submitted_at TEXT
);

CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY,
    admin_id INTEGER REFERENCES admins(id) ON DELETE SET NULL,
    student_id INTEGER REFERENCES students(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_students_course_batch ON students(course, batch);
CREATE INDEX IF NOT EXISTS idx_student_tasks_student_status ON student_tasks(student_id, status);
CREATE INDEX IF NOT EXISTS idx_student_tasks_deadline ON student_tasks(deadline);
CREATE INDEX IF NOT EXISTS idx_reports_student_created ON reports(student_id, created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_user_role ON sessions(user_id, role, expires_at);
CREATE INDEX IF NOT EXISTS idx_student_skills_student_mastery
    ON student_skills(student_id, mastery_score);
CREATE INDEX IF NOT EXISTS idx_student_practice_student_expiry
    ON student_practice_sessions(student_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_activity_log_created ON activity_log(created_at);
