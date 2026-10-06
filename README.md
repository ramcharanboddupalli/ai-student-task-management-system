# AI Student Task Management System — Powered by Skillonex Academy

The project uses FastAPI, React, SQLite, signed server-side sessions, fictional seed data, and a centralized Groq integration. Phase 2 implements the Admin panel; Phase 3A adds the Student dashboard and task center; Phase 3B adds five data-grounded Student AI learning features.

## Requirements

- Python 3.11 or newer
- Node.js 20.19+ or 22.12+
- npm

## Backend setup (Windows PowerShell)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
```

Set a unique, high-entropy `SESSION_SECRET` in your local `.env` before starting the backend. Startup fails clearly if it is missing. `GROQ_API_KEY` and `GROQ_MODEL` are optional until AI features are used. No Groq request is made on startup; AI health reports only whether a key is configured.

Start the backend from the project root:

```powershell
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

The backend creates `database\skillonex.db`, initializes or migrates its schema, and inserts demo data on startup. Seeding is idempotent. Demo student passwords use the documented demo format: the cleaned full name followed by the registration number. Student passwords are stored only as Argon2 hashes.

## Frontend setup

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The Vite development server proxies `/api` requests to the backend.

## Verification endpoints

- API health: <http://127.0.0.1:8000/api/v1/health>
- SQLite health: <http://127.0.0.1:8000/api/v1/health/database>
- AI configuration status (boolean only): <http://127.0.0.1:8000/api/v1/health/ai>
- OpenAPI docs: <http://127.0.0.1:8000/docs>

The first Admin account can be created once through `POST /api/v1/auth/admin/signup`; subsequent signups are closed. The backend uses Argon2 password hashes and signed, HttpOnly, SameSite=Strict session cookies with server-side revocation. Set `COOKIE_SECURE=true` when serving over HTTPS.

## Admin panel (Phase 2)

After starting the backend and frontend, open <http://localhost:5173> and create the first Admin account. The Admin workspace provides:

- A dashboard with metrics calculated from SQLite records.
- Student directory, search and filters, profiles, and Admin-managed enrollment lifecycle.
- Task drafting through Groq with an explicit review step before saving or assignment.
- Performance and risk indicators calculated from recorded task activity, with optional Groq-generated actions.
- Batch metrics and trends, plus optional AI insights.
- A scoped Admin Copilot and generated reports grounded in academy records.

Configure `GROQ_API_KEY` in the local `.env` only when you choose to use AI-dependent features. Without it, those operations return a clear service-unavailable response; deterministic Admin features remain available. The application does not create `.env` files or generate credentials automatically.

## Student panel (Phases 3A and 3B)

Students sign in with Admin-created accounts; there is no student self-registration. The Student workspace is restricted to the authenticated student's own profile, assigned tasks, and progress. Its dashboard shows database-calculated task counts, completion, deadlines, current level, and today's deterministic task priority.

After sign-in, students land on `/student/dashboard`. The dashboard includes the authenticated student's current progress, next priority, upcoming deadlines, quick task actions, AI Daily Insight, and AI Task Prioritization. `/student/tasks` opens the Smart Task Center. Student navigation also provides `/student/assistant`, `/student/coach`, `/student/planner`, `/student/practice`, and `/student/report`.

The Smart Task Center displays only assigned tasks and supports status filtering plus the forward status flow `Pending` → `In Progress` → `Completed`. The backend checks assignment ownership and transition validity for every status change. Students cannot assign, delete, or redefine Admin-managed tasks.

Optional AI features use the centralized Groq service with the authenticated student's recorded profile and tasks:

- `GET /api/v1/student/insights/daily` creates a structured daily insight.
- `POST /api/v1/student/tasks/prioritization` ranks the student's own outstanding assignments. It only recommends an order and never changes status.
- `POST /api/v1/student/assistant` answers learning questions using only the authenticated student's profile, tasks, progress, and recorded skills. Numeric percentages are returned only when they match and are labeled as the corresponding recorded metric; unsupported percentages and dates are rejected.
- `POST /api/v1/student/coach` interprets deterministic progress and topic data to suggest strengths, focus areas, and a next step.
- `POST /api/v1/student/planner` creates an advisory schedule from the student's actual open tasks and requested study availability; it does not change task statuses or deadlines.
- `GET /api/v1/student/practice/topics` returns topics from the student's assigned tasks and recorded skills. `POST /api/v1/student/practice/generate` creates questions without returning answers; `POST /api/v1/student/practice/{practice_id}/submit` evaluates and reveals answer explanations after submission.
- `POST /api/v1/student/report` generates and saves a progress report in the existing SQLite `reports` table. `GET /api/v1/student/report/history` returns only that student's saved reports.

Practice answer keys are held in short-lived, student-scoped SQLite practice sessions and removed after evaluation. No long-term practice history is stored. Without a configured Groq key, AI-dependent operations return a clear service-unavailable response. Deterministic dashboard data and task management remain available.

## Tests and build

From the project root:

```powershell
python -m pytest backend\tests -q
cd frontend
npm run build
npm run lint
```

## Boundaries

The centralized Groq service uses the official Groq SDK and raises an explicit configuration error when no key is configured. Dashboard, performance, batch, planner scheduling, report metrics, and student progress figures are computed from SQLite records/application logic, not generated by an LLM. The AI features interpret or explain those facts and never execute generated SQL.
