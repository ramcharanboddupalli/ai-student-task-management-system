import { useCallback, useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import {
  Link,
  NavLink,
  Outlet,
  Route,
  Routes,
  useNavigate,
  useParams,
} from 'react-router-dom'
import { ApiError, request } from './services/api'
import './AdminPanel.css'

type AdminDashboard = {
  total_students: number
  active_tasks: number
  completed_tasks: number
  completion_rate: number
  pending_tasks: number
  overdue_tasks: number
  overall_performance: number | null
  batch_overview: Array<{
    batch: string
    student_count: number
    completion_rate: number
    overdue_count: number
  }>
  recent_activity: Array<{ id: number; event_type: string; summary: string; created_at: string }>
}

type Student = {
  id: number
  student_id: string
  registration_number: string
  full_name: string
  email: string | null
  course: string
  batch: string
  current_level: string
  is_active: boolean
  total_tasks: number
  completed_tasks: number
  overdue_tasks: number
  completion_percentage: number
  performance_average: number | null
}

type Profile = {
  student: Student
  metrics: {
    total_tasks: number
    completed_tasks: number
    pending_tasks: number
    in_progress_tasks: number
    overdue_tasks: number
    recent_completions_30d: number
    previous_completions_30d: number
    completion_percentage: number
    performance_average: number | null
  }
  tasks: Array<{
    assignment_id: number
    title: string
    topic: string
    difficulty: string
    status: string
    deadline: string
    performance_score: number | null
  }>
  skills: Array<{ topic: string; mastery_score: number }>
}

type Task = {
  id: number
  title: string
  description: string
  topic: string
  course: string
  difficulty: string
  priority: string
  estimated_minutes: number
  requirements: string[]
  expected_outcome: string
  evaluation_criteria: string[]
  assigned_count: number
}

type Performance = {
  id: number
  student_id: string
  full_name: string
  course: string
  batch: string
  classification: string
  metrics: {
    completion_percentage: number
    pending_tasks: number
    overdue_tasks: number
    performance_average: number | null
    completion_trend: string
  }
  reasons: string[]
  suggested_action: string
}

type Batch = {
  batch: string
  student_count: number
  average_completion: number
  average_performance: number | null
  pending_tasks: number
  overdue_tasks: number
  strong_topics: Array<{ topic: string; average_mastery: number }>
  weak_topics: Array<{ topic: string; average_mastery: number }>
  topic_mastery: Array<{ topic: string; average_mastery: number; student_count: number }>
  difficulty_patterns: Array<{
    difficulty: string
    assignments: number
    completed: number
    average_performance: number | null
  }>
  students_needing_support: Array<{
    full_name: string
    student_id: string
    classification: string
    metrics: { completion_percentage: number; overdue_tasks: number }
  }>
  weekly_trend: Array<{ week: string | null; assigned: number; completed: number }>
}

type Report = {
  id: number
  report_type: string
  created_at: string
  full_name: string | null
  content: {
    ai_analysis?: { title: string; summary: string; insights: string[]; recommendations: string[] }
  }
}

type StudentAnalysis = {
  current_level: string
  source: string
  strengths: string[]
  weak_areas: string[]
  learning_gaps: string[]
  recommended_actions: string[]
}

type AiInsight = {
  headline: string
  summary: string
  positive_progress: string
  students_needing_attention: number[]
  common_weakness: string
  recommended_admin_action: string
}

function useResource<T>(path: string) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setData(await request<T>(path))
    } catch (resourceError) {
      if (resourceError instanceof ApiError && resourceError.status === 401) return
      setError(resourceError instanceof Error ? resourceError.message : 'Unable to load data.')
    } finally {
      setLoading(false)
    }
  }, [path])
  useEffect(() => {
    let mounted = true
    request<T>(path)
      .then((result) => { if (mounted) { setData(result); setError('') } })
      .catch((resourceError: unknown) => {
        if (mounted && !(resourceError instanceof ApiError && resourceError.status === 401)) {
          setError(resourceError instanceof Error ? resourceError.message : 'Unable to load data.')
        }
      })
      .finally(() => { if (mounted) setLoading(false) })
    return () => { mounted = false }
  }, [path])
  return { data, setData, loading, error, refresh }
}

function Notice({ children, kind = 'info' }: { children: ReactNode; kind?: 'info' | 'error' | 'success' }) {
  return <div className={`admin-notice ${kind}`} role={kind === 'error' ? 'alert' : 'status'}>{children}</div>
}

function PageHeader({ eyebrow, title, description, action }: {
  eyebrow: string
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="admin-page-header">
      <div><p className="admin-eyebrow">{eyebrow}</p><h1>{title}</h1><p>{description}</p></div>
      {action}
    </div>
  )
}

function AdminLayout() {
  const navigate = useNavigate()
  const [ready, setReady] = useState(false)
  const [authError, setAuthError] = useState('')
  const [navOpen, setNavOpen] = useState(false)
  useEffect(() => {
    let mounted = true
    request<{ role: string }>('/api/v1/auth/me')
      .then((user) => {
        if (!mounted) return
        if (user.role !== 'admin') navigate('/student/login', { replace: true })
        else setReady(true)
      })
      .catch(() => {
        if (mounted) navigate('/admin/login', { replace: true })
      })
    return () => { mounted = false }
  }, [navigate])

  async function signOut() {
    setAuthError('')
    try {
      await request('/api/v1/auth/logout', { method: 'POST' })
      navigate('/', { replace: true })
    } catch (logoutError) {
      setAuthError(logoutError instanceof Error ? logoutError.message : 'Could not sign out.')
    }
  }

  if (!ready) return <div className="admin-loading" role="status">Checking administrator session…</div>
  return (
    <div className={`admin-app${navOpen ? ' nav-open' : ''}`}>
      <aside className="admin-sidebar">
        <div className="admin-sidebar-head">
          <Link to="/" className="admin-brand"><span className="admin-brand-mark">S</span><span>Skillonex<small>ACADEMY</small></span></Link>
          <button className="admin-menu-close" type="button" aria-label="Close navigation" onClick={() => setNavOpen(false)}>×</button>
        </div>
        <p className="sidebar-caption">ADMINISTRATION</p>
        <nav aria-label="Admin features" className="admin-nav">
          <NavLink end to="/admin" onClick={() => setNavOpen(false)}><span>01</span> AI Command Dashboard</NavLink>
          <NavLink to="/admin/students" onClick={() => setNavOpen(false)}><span>02</span> Student Management + AI Profile</NavLink>
          <NavLink to="/admin/tasks" onClick={() => setNavOpen(false)}><span>03</span> AI Task Creator & Assignment</NavLink>
          <NavLink to="/admin/performance" onClick={() => setNavOpen(false)}><span>04</span> AI Performance & Risk</NavLink>
          <NavLink to="/admin/batches" onClick={() => setNavOpen(false)}><span>05</span> AI Batch Intelligence</NavLink>
          <NavLink to="/admin/copilot" onClick={() => setNavOpen(false)}><span>06</span> AI Copilot + Smart Reports</NavLink>
        </nav>
        <div className="sidebar-bottom">
          <div className="admin-status"><span /> Admin workspace</div>
          <button className="admin-signout" onClick={signOut}>Sign out <span aria-hidden="true">↗</span></button>
        </div>
      </aside>
      {navOpen && <button className="admin-mobile-backdrop" type="button" aria-label="Close navigation" onClick={() => setNavOpen(false)} />}
      <main className="admin-main">
        <header className="admin-topbar">
          <button className="admin-menu-toggle" type="button" aria-label="Open navigation" aria-expanded={navOpen} onClick={() => setNavOpen(true)}>☰</button>
          <span>Skillonex Academy <b>/</b> Admin</span><span>Learning operations</span>
        </header>
        {authError && <Notice kind="error">{authError}</Notice>}
        <div className="admin-content">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

function DashboardPage() {
  const { data, loading, error } = useResource<AdminDashboard>('/api/v1/admin/dashboard')
  const [insight, setInsight] = useState<AiInsight | null>(null)
  const [aiError, setAiError] = useState('')
  const [aiLoading, setAiLoading] = useState(false)

  async function loadInsight() {
    setAiLoading(true)
    setAiError('')
    try { setInsight(await request<AiInsight>('/api/v1/admin/insights/daily')) }
    catch (requestError) { setAiError(requestError instanceof Error ? requestError.message : 'AI insight unavailable.') }
    finally { setAiLoading(false) }
  }

  return (
    <>
      <PageHeader eyebrow="FEATURE 01 · ADMIN COMMAND" title="Learning at a glance" description="A live operational view calculated from academy records." />
      {loading && <Notice>Loading current academy metrics…</Notice>}
      {error && <Notice kind="error">{error}</Notice>}
      {data && <>
        <div className="admin-metric-grid">
          <Metric label="Total students" value={data.total_students} detail="Active enrollments" />
          <Metric label="Active tasks" value={data.active_tasks} detail="Assigned, not completed" />
          <Metric label="Completion rate" value={`${data.completion_rate}%`} detail={`${data.completed_tasks} completed assignments`} />
          <Metric label="Pending tasks" value={data.pending_tasks} detail="Awaiting a start" />
          <Metric label="Overdue tasks" value={data.overdue_tasks} detail="Past deadline, not complete" tone={data.overdue_tasks ? 'alert' : 'normal'} />
          <Metric label="Overall performance" value={data.overall_performance === null ? '—' : `${data.overall_performance}%`} detail="Mean of recorded scores" />
        </div>
        <div className="admin-dashboard-columns">
          <section className="admin-panel-card">
            <div className="section-heading"><div><p className="admin-eyebrow">COHORTS</p><h2>Batch overview</h2></div><NavLink to="/admin/batches">Explore batches ↗</NavLink></div>
            {!data.batch_overview.length ? <EmptyState text="No active student batches are recorded yet." /> :
              <div className="batch-overview-list">{data.batch_overview.map((batch) => <div className="batch-overview-row" key={batch.batch}>
                <div><strong>{batch.batch}</strong><small>{batch.student_count} students · {batch.overdue_count} overdue</small></div>
                <div className="mini-progress"><span style={{ width: `${batch.completion_rate}%` }} /></div><b>{batch.completion_rate}%</b>
              </div>)}</div>}
          </section>
          <section className="admin-panel-card">
            <div className="section-heading"><div><p className="admin-eyebrow">RECENT CHANGES</p><h2>Activity</h2></div></div>
            {!data.recent_activity.length ? <EmptyState text="No recent activity is recorded." /> :
              <ul className="activity-list">{data.recent_activity.map((entry) => <li key={`${entry.event_type}-${entry.id}`}><span className="activity-dot" /><div><p>{entry.summary}</p><small>{new Date(`${entry.created_at.replace(' ', 'T')}Z`).toLocaleString()}</small></div></li>)}</ul>}
          </section>
        </div>
        <section className="ai-insight-card">
          <div className="ai-orb">✦</div>
          <div className="ai-insight-content">
            <p className="admin-eyebrow">GROQ · DATABASE-GROUNDED</p><h2>Daily academy insight</h2>
            <p>AI interprets recorded student, task, and score data. It does not calculate dashboard metrics.</p>
            {aiError && <Notice kind="error">{aiError}</Notice>}
            {insight && <div className="ai-insight-result"><strong>{insight.headline}</strong><p>{insight.summary}</p><div className="ai-insight-detail"><span><b>Positive signal</b>{insight.positive_progress}</span><span><b>Weakness signal</b>{insight.common_weakness}</span><span><b>Suggested action</b>{insight.recommended_admin_action}</span></div></div>}
          </div>
          <button className="admin-button primary" disabled={aiLoading} onClick={loadInsight}>{aiLoading ? 'Analyzing…' : insight ? 'Refresh insight' : 'Generate insight'}</button>
        </section>
      </>}
    </>
  )
}

function Metric({ label, value, detail, tone = 'normal' }: { label: string; value: string | number; detail: string; tone?: string }) {
  return <article className={`admin-metric ${tone}`}><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>
}

function EmptyState({ text }: { text: string }) { return <p className="admin-empty">{text}</p> }

function localDateInputValue() {
  const date = new Date()
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset())
  return date.toISOString().slice(0, 10)
}

function StudentsPage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [batchFilter, setBatchFilter] = useState('')
  const [courseFilter, setCourseFilter] = useState('')
  const [activeFilter, setActiveFilter] = useState('true')
  const filterOptions = useResource<{ courses: string[]; batches: string[] }>('/api/v1/admin/student-filters')
  const params = new URLSearchParams()
  if (query) params.set('search', query)
  if (batchFilter) params.set('batch', batchFilter)
  if (courseFilter) params.set('course', courseFilter)
  if (activeFilter) params.set('active', activeFilter)
  const { data, loading, error, refresh } = useResource<Student[]>(`/api/v1/admin/students?${params}`)
  const [createOpen, setCreateOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [failure, setFailure] = useState('')
  const [credential, setCredential] = useState<{ student: Student; password: string } | null>(null)

  async function createStudent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true); setFailure(''); setMessage('')
    const values = Object.fromEntries(new FormData(event.currentTarget).entries())
    if (!values.email) delete values.email
    try {
      const result = await request<{ student: Student; initial_password: string }>('/api/v1/admin/students', {
        method: 'POST', body: JSON.stringify(values),
      })
      setCredential({ student: result.student, password: result.initial_password })
      setCreateOpen(false)
      setMessage('Student created. Copy the initial credential now; it will not be shown again.')
      void refresh()
    } catch (createError) { setFailure(createError instanceof Error ? createError.message : 'Could not create student.') }
    finally { setBusy(false) }
  }

  return <>
    <PageHeader eyebrow="FEATURE 02 · STUDENT MANAGEMENT" title="Students" description="Manage enrollments, see progress, and open evidence-based learner profiles."
      action={<button className="admin-button primary" onClick={() => setCreateOpen(true)}>＋ Add student</button>} />
    <div className="student-toolbar">
      <label className="search-field"><span aria-hidden="true">⌕</span><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search name, student ID, registration…" aria-label="Search students" /></label>
      <select value={courseFilter} onChange={(e) => setCourseFilter(e.target.value)} aria-label="Filter by course"><option value="">All courses</option>{(filterOptions.data?.courses ?? []).map((course) => <option key={course}>{course}</option>)}</select>
      <select value={batchFilter} onChange={(e) => setBatchFilter(e.target.value)} aria-label="Filter by batch"><option value="">All batches</option>{(filterOptions.data?.batches ?? []).map((batch) => <option key={batch}>{batch}</option>)}</select>
      <select value={activeFilter} onChange={(e) => setActiveFilter(e.target.value)} aria-label="Filter by enrollment status"><option value="true">Active students</option><option value="false">Inactive students</option><option value="">All students</option></select>
    </div>
    {message && <Notice kind="success">{message}</Notice>}{failure && <Notice kind="error">{failure}</Notice>}
    {loading && <Notice>Loading student records…</Notice>}{error && <Notice kind="error">{error}</Notice>}
    {data && !data.length && <EmptyState text="No students match these filters." />}
    {data && data.length > 0 && <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Student</th><th>Course / batch</th><th>Progress</th><th>Performance</th><th>Status</th><th /></tr></thead><tbody>
      {data.map((student) => <tr key={student.id} onClick={() => navigate(`/admin/students/${student.id}`)} className="clickable-row">
        <td><strong>{student.full_name}</strong><small>{student.student_id}</small></td><td>{student.course}<small>{student.batch}</small></td>
        <td><div className="table-progress"><span>{student.completion_percentage}%</span><div className="mini-progress"><i style={{ width: `${student.completion_percentage}%` }} /></div></div><small>{student.completed_tasks}/{student.total_tasks} complete</small></td>
        <td>{student.performance_average === null ? '—' : `${student.performance_average}%`}</td><td><span className={`status-pill ${student.is_active ? 'active' : 'inactive'}`}>{student.is_active ? 'Active' : 'Inactive'}</span></td><td><span aria-hidden="true">↗</span></td>
      </tr>)}
    </tbody></table></div>}
    {createOpen && <Modal title="Add a student" onClose={() => setCreateOpen(false)}><form className="admin-form" onSubmit={createStudent}>
      <div className="form-grid"><label>Full name<input name="full_name" required minLength={2} maxLength={120} /></label><label>Registration number<input name="registration_number" required minLength={2} maxLength={50} /></label>
        <label>Email (optional)<input name="email" type="email" /></label><label>Course<input name="course" required placeholder="e.g. Python Development" /></label>
        <label>Batch<input name="batch" required placeholder="e.g. PY-2026-A" /></label><label>Current level<select name="current_level"><option>Beginner</option><option>Intermediate</option><option>Advanced</option></select></label></div>
      <p className="form-help">Student ID and initial password are generated from the course, name, and registration number. The password is shown once after creation.</p>
      {failure && <Notice kind="error">{failure}</Notice>}<div className="modal-actions"><button type="button" className="admin-button quiet" onClick={() => setCreateOpen(false)}>Cancel</button><button className="admin-button primary" disabled={busy}>{busy ? 'Creating…' : 'Create student'}</button></div>
    </form></Modal>}
    {credential && <Modal title="Student created" onClose={() => setCredential(null)}><div className="credential-card"><p>Give this initial password to <strong>{credential.student.full_name}</strong>. It will not be displayed again after closing.</p><span>Student ID</span><code>{credential.student.student_id}</code><span>Initial password</span><code>{credential.password}</code><button className="admin-button primary" onClick={() => { void navigator.clipboard.writeText(`Student ID: ${credential.student.student_id}\nInitial password: ${credential.password}`) }}>Copy credentials</button></div></Modal>}
  </>
}

function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}><section className="admin-modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div className="modal-heading"><h2 id="modal-title">{title}</h2><button className="icon-button" onClick={onClose} aria-label="Close dialog">×</button></div>{children}</section></div>
}

function StudentProfilePage() {
  const { studentId } = useParams()
  const id = Number(studentId)
  const { data, loading, error, refresh } = useResource<Profile>(`/api/v1/admin/students/${id}`)
  const [analysis, setAnalysis] = useState<StudentAnalysis | null>(null)
  const [aiError, setAiError] = useState('')
  const [aiBusy, setAiBusy] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const navigate = useNavigate()

  async function analyze() {
    setAiBusy(true); setAiError('')
    try { setAnalysis(await request<StudentAnalysis>(`/api/v1/admin/students/${id}/ai-profile`, { method: 'POST' })) }
    catch (requestError) { setAiError(requestError instanceof Error ? requestError.message : 'AI analysis unavailable.') }
    finally { setAiBusy(false) }
  }
  async function toggleActive() {
    if (!data) return
    const action = data.student.is_active ? 'deactivate' : 'activate'
    if (action === 'deactivate' && !window.confirm(`Deactivate ${data.student.full_name}?`)) return
    try {
      await request(`/api/v1/admin/students/${id}/${action}`, { method: 'POST' })
      void refresh()
    } catch (requestError) { setAiError(requestError instanceof Error ? requestError.message : 'Could not update enrollment.') }
  }
  async function remove() {
    if (!data || !window.confirm(`Permanently delete ${data.student.full_name} and assigned records?`)) return
    try { await request(`/api/v1/admin/students/${id}`, { method: 'DELETE' }); navigate('/admin/students') }
    catch (requestError) { setAiError(requestError instanceof Error ? requestError.message : 'Could not delete student.') }
  }
  async function update(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const values = Object.fromEntries(new FormData(event.currentTarget).entries())
    if (!values.email) delete values.email
    try {
      await request(`/api/v1/admin/students/${id}`, { method: 'PUT', body: JSON.stringify(values) })
      setEditOpen(false); void refresh()
    } catch (requestError) { setAiError(requestError instanceof Error ? requestError.message : 'Could not update profile.') }
  }

  if (loading) return <Notice>Loading student profile…</Notice>
  if (error || !data) return <Notice kind="error">{error || 'Student not found.'}</Notice>
  const student = data.student
  return <>
    <Link to="/admin/students" className="admin-backlink">← All students</Link>
    <PageHeader eyebrow="STUDENT PROFILE" title={student.full_name} description={`${student.student_id} · ${student.course} · ${student.batch}`}
      action={<div className="profile-actions"><button className="admin-button quiet" onClick={() => setEditOpen(true)}>Edit profile</button><button className="admin-button quiet" onClick={toggleActive}>{student.is_active ? 'Deactivate' : 'Reactivate'}</button><button className="admin-button danger" onClick={remove}>Delete</button></div>} />
    {aiError && <Notice kind="error">{aiError}</Notice>}
    <div className="profile-metrics"><Metric label="Completion" value={`${data.metrics.completion_percentage}%`} detail={`${data.metrics.completed_tasks} / ${data.metrics.total_tasks} tasks`} /><Metric label="Pending" value={data.metrics.pending_tasks} detail="Assigned, not started" /><Metric label="Overdue" value={data.metrics.overdue_tasks} detail="Past deadline" tone={data.metrics.overdue_tasks ? 'alert' : 'normal'} /><Metric label="Recent progress" value={data.metrics.recent_completions_30d} detail={`Completed in 30d · ${data.metrics.previous_completions_30d} prior 30d`} /><Metric label="Performance" value={data.metrics.performance_average === null ? '—' : `${data.metrics.performance_average}%`} detail="Mean of scored tasks" /></div>
    <div className="admin-dashboard-columns profile-columns">
      <section className="admin-panel-card"><div className="section-heading"><div><p className="admin-eyebrow">ASSIGNMENTS</p><h2>Task history</h2></div></div>
        {!data.tasks.length ? <EmptyState text="No tasks have been assigned." /> : <div className="profile-task-list">{data.tasks.map((task) => <div key={task.assignment_id}><div><strong>{task.title}</strong><small>{task.topic} · {task.difficulty}</small></div><span className={`status-pill ${task.status.toLowerCase().replace(' ', '-')}`}>{task.status}</span><time>{task.deadline}</time><b>{task.performance_score === null ? '—' : `${task.performance_score}%`}</b></div>)}</div>}
      </section>
      <section className="admin-panel-card"><div className="section-heading"><div><p className="admin-eyebrow">RECORDED SIGNALS</p><h2>Topic mastery</h2></div></div>
        {!data.skills.length ? <EmptyState text="No topic mastery records are available." /> : data.skills.map((skill) => <div className="mastery-row" key={skill.topic}><div><span>{skill.topic}</span><b>{skill.mastery_score}%</b></div><div className="mastery-track"><i style={{ width: `${skill.mastery_score}%` }} /></div></div>)}
      </section>
    </div>
    <section className="ai-insight-card profile-ai"><div className="ai-orb">✦</div><div className="ai-insight-content"><p className="admin-eyebrow">AI PROFILE · GROQ</p><h2>Evidence-based learner analysis</h2><p>Generated from this student's recorded tasks, scores, and topic mastery.</p>
      {analysis && <div className="profile-analysis-grid">{[['Strengths', analysis.strengths], ['Weak areas', analysis.weak_areas], ['Learning gaps', analysis.learning_gaps], ['Recommended actions', analysis.recommended_actions]].map(([title, items]) => <div key={String(title)}><b>{title}</b>{(items as string[]).length ? <ul>{(items as string[]).map((item) => <li key={item}>{item}</li>)}</ul> : <small>Insufficient recorded evidence.</small>}</div>)}</div>}
    </div><button className="admin-button primary" onClick={analyze} disabled={aiBusy}>{aiBusy ? 'Analyzing…' : analysis ? 'Refresh analysis' : 'Analyze profile'}</button></section>
    {editOpen && <Modal title="Update student profile" onClose={() => setEditOpen(false)}><form className="admin-form" onSubmit={update}><div className="form-grid">
      <label>Full name<input name="full_name" defaultValue={student.full_name} required /></label><label>Email<input name="email" type="email" defaultValue={student.email ?? ''} /></label><label>Course<input name="course" defaultValue={student.course} required /></label><label>Batch<input name="batch" defaultValue={student.batch} required /></label><label>Current level<select name="current_level" defaultValue={student.current_level}><option>Beginner</option><option>Intermediate</option><option>Advanced</option></select></label>
    </div><div className="modal-actions"><button type="button" className="admin-button quiet" onClick={() => setEditOpen(false)}>Cancel</button><button className="admin-button primary">Save changes</button></div></form></Modal>}
  </>
}

function TaskStudioPage() {
  const { data: tasks, loading, error, refresh } = useResource<Task[]>('/api/v1/admin/tasks')
  const [draft, setDraft] = useState<Partial<Task> | null>(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [failure, setFailure] = useState('')
  const [saved, setSaved] = useState<Task | null>(null)
  const [taskContext, setTaskContext] = useState<{ topic: string; course: string; level: string } | null>(null)
  const [recommendations, setRecommendations] = useState<Array<{ id: number; full_name: string; student_id: string; rationale: string }>>([])
  const [selected, setSelected] = useState<number[]>([])
  const [deadline, setDeadline] = useState('')

  async function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setFailure(''); setNotice(''); setSaved(null)
    const form = new FormData(event.currentTarget)
    const payload = {
      topic: String(form.get('topic') ?? ''),
      course: String(form.get('course') ?? ''),
      level: String(form.get('level') ?? 'Beginner'),
      goal: String(form.get('goal') ?? ''),
      requirements: String(form.get('requirements') ?? '').split('\n').map((item) => item.trim()).filter(Boolean),
    }
    setTaskContext({ topic: payload.topic, course: payload.course, level: payload.level })
    try { setDraft(await request<Partial<Task>>('/api/v1/admin/tasks/generate', { method: 'POST', body: JSON.stringify(payload) })) }
    catch (requestError) { setFailure(requestError instanceof Error ? requestError.message : 'Could not generate a task draft.') }
    finally { setBusy(false) }
  }
  async function approve() {
    if (!draft || !taskContext) return
    setBusy(true); setFailure('')
    const taskPayload = {
      ...draft,
      topic: taskContext.topic,
      course: taskContext.course,
      priority: 'Normal',
    }
    try {
      const task = await request<Task>('/api/v1/admin/tasks', { method: 'POST', body: JSON.stringify(taskPayload) })
      setSaved(task); setDraft(null); void refresh()
    } catch (requestError) { setFailure(requestError instanceof Error ? requestError.message : 'Could not save the approved task.') }
    finally { setBusy(false) }
  }
  async function suggest() {
    if (!saved) return
    setBusy(true); setFailure('')
    try {
      const result = await request<{ recommendations: typeof recommendations }>(`/api/v1/admin/tasks/${saved.id}/recommendations`, {
        method: 'POST', body: JSON.stringify({ topic: saved.topic, course: saved.course, level: saved.difficulty }),
      })
      setRecommendations(result.recommendations)
    } catch (requestError) { setFailure(requestError instanceof Error ? requestError.message : 'Could not get recommendations.') }
    finally { setBusy(false) }
  }
  async function assign() {
    if (!saved || !deadline || !selected.length) return
    setBusy(true); setFailure('')
    try {
      const result = await request<{ assigned_count: number }>(`/api/v1/admin/tasks/${saved.id}/assign`, {
        method: 'POST', body: JSON.stringify({ student_ids: selected, deadline }),
      })
      setNotice(`Assigned to ${result.assigned_count} student(s).`)
      setRecommendations([]); setSelected([]); setSaved(null); void refresh()
    } catch (requestError) { setFailure(requestError instanceof Error ? requestError.message : 'Could not assign task.') }
    finally { setBusy(false) }
  }
  function updateDraft(key: string, value: string | string[]) { setDraft((current) => current ? { ...current, [key]: value } : current) }

  return <>
    <PageHeader eyebrow="FEATURE 03 · TASK CREATION & ASSIGNMENT" title="Task studio" description="Draft with Groq, review every field, then approve and assign using academy records." />
    {failure && <Notice kind="error">{failure}</Notice>}{notice && <Notice kind="success">{notice}</Notice>}
    <div className="task-studio-grid">
      <section className="admin-panel-card"><div className="section-heading"><div><p className="admin-eyebrow">01 · SET THE LEARNING INTENT</p><h2>Generate a task draft</h2></div></div>
        <form className="admin-form" onSubmit={generate}><label>Topic<input name="topic" required minLength={2} placeholder="e.g. Data visualization" /></label><label>Course<input name="course" required minLength={2} placeholder="e.g. Data Analytics" /></label><label>Level<select name="level"><option>Beginner</option><option>Intermediate</option><option>Advanced</option></select></label><label>Learning goal<textarea name="goal" required minLength={10} rows={3} placeholder="What should the learner be able to do?" /></label><label>Optional requirements<textarea name="requirements" rows={2} placeholder="One requirement per line" /></label><button className="admin-button primary" disabled={busy}>{busy ? 'Generating…' : 'Generate with Groq'}</button></form>
        <p className="form-help">AI generation requires a configured Groq key. Nothing is saved or assigned until you approve the reviewed draft.</p>
      </section>
      <section className="admin-panel-card task-approval-card"><div className="section-heading"><div><p className="admin-eyebrow">02 · REVIEW & APPROVE</p><h2>{draft ? 'Review generated draft' : saved ? 'Ready to assign' : 'Task approval'}</h2></div></div>
        {!draft && !saved && <EmptyState text="Generated task drafts appear here for review before they are saved." />}
        {draft && <div className="draft-review"><label>Title<input required minLength={4} maxLength={160} value={draft.title ?? ''} onChange={(e) => updateDraft('title', e.target.value)} /></label><label>Description<textarea required minLength={20} maxLength={3000} rows={4} value={draft.description ?? ''} onChange={(e) => updateDraft('description', e.target.value)} /></label><div className="form-grid"><label>Difficulty<select value={draft.difficulty} onChange={(e) => updateDraft('difficulty', e.target.value)}><option>Beginner</option><option>Intermediate</option><option>Advanced</option></select></label><label>Estimated minutes<input type="number" required min={10} max={480} value={draft.estimated_minutes ?? 60} onChange={(e) => updateDraft('estimated_minutes', e.target.value)} /></label></div><label>Requirements<textarea required rows={3} value={(draft.requirements ?? []).join('\n')} onChange={(e) => updateDraft('requirements', e.target.value.split('\n').map((item) => item.trim()).filter(Boolean))} /></label><label>Expected outcome<textarea required minLength={8} maxLength={1000} value={draft.expected_outcome ?? ''} onChange={(e) => updateDraft('expected_outcome', e.target.value)} /></label><label>Evaluation criteria<textarea required value={(draft.evaluation_criteria ?? []).join('\n')} onChange={(e) => updateDraft('evaluation_criteria', e.target.value.split('\n').map((item) => item.trim()).filter(Boolean))} /></label><div className="modal-actions"><button className="admin-button quiet" onClick={() => setDraft(null)}>Discard</button><button className="admin-button primary" disabled={busy} onClick={approve}>Approve & save task</button></div></div>}
        {saved && <div className="saved-task"><span className="status-pill active">Saved · not assigned</span><h3>{saved.title}</h3><p>{saved.course} · {saved.difficulty} · {saved.estimated_minutes} min</p><button className="admin-button quiet" disabled={busy} onClick={suggest}>Recommend students</button>
          {recommendations.length > 0 && <><p className="form-help">AI recommendations are suggestions only. Select the students to assign.</p>{recommendations.map((item) => <label className="recommendation-row" key={item.id}><input type="checkbox" checked={selected.includes(item.id)} onChange={(e) => setSelected((current) => e.target.checked ? [...current, item.id] : current.filter((id) => id !== item.id))} /><span><b>{item.full_name} · {item.student_id}</b><small>{item.rationale}</small></span></label>)}<label>Deadline<input type="date" min={localDateInputValue()} value={deadline} onChange={(e) => setDeadline(e.target.value)} /></label><button className="admin-button primary" disabled={busy || !selected.length || !deadline} onClick={assign}>Approve assignment</button></>}
        </div>}
      </section>
    </div>
    <section className="admin-panel-card task-library"><div className="section-heading"><div><p className="admin-eyebrow">RECORDED TASKS</p><h2>Task library</h2></div></div>{loading && <Notice>Loading tasks…</Notice>}{error && <Notice kind="error">{error}</Notice>}{!loading && tasks?.length === 0 && <EmptyState text="No tasks have been created." />}{tasks && tasks.length > 0 && <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Task</th><th>Course</th><th>Difficulty</th><th>Estimate</th><th>Assigned</th></tr></thead><tbody>{tasks.map((task) => <tr key={task.id}><td><strong>{task.title}</strong><small>{task.topic}</small></td><td>{task.course}</td><td>{task.difficulty}</td><td>{task.estimated_minutes} min</td><td>{task.assigned_count}</td></tr>)}</tbody></table></div>}</section>
  </>
}

function PerformancePage() {
  const { data, loading, error } = useResource<Performance[]>('/api/v1/admin/performance')
  const [analyzed, setAnalyzed] = useState<Performance[] | null>(null)
  const [aiError, setAiError] = useState('')
  const [busy, setBusy] = useState(false)
  async function analyze() {
    setBusy(true); setAiError('')
    try { setAnalyzed((await request<{ students: Performance[] }>('/api/v1/admin/performance/analyze', { method: 'POST' })).students) }
    catch (requestError) { setAiError(requestError instanceof Error ? requestError.message : 'AI analysis unavailable.') }
    finally { setBusy(false) }
  }
  const rows = analyzed ?? data
  return <>
    <PageHeader eyebrow="FEATURE 04 · PERFORMANCE & RISK" title="Learner pulse" description="Risk classifications and metrics are computed from actual task and score records." action={<button className="admin-button primary" onClick={analyze} disabled={busy}>{busy ? 'Analyzing…' : 'Generate AI actions'}</button>} />
    {loading && <Notice>Calculating performance and risk…</Notice>}{error && <Notice kind="error">{error}</Notice>}{aiError && <Notice kind="error">{aiError}</Notice>}
    {rows && !rows.length && <EmptyState text="No active student records are available for analysis." />}
    {rows && rows.length > 0 && <div className="risk-list">{rows.map((student) => <article className="risk-card" key={student.id}><div className="risk-heading"><div><span className={`risk-pill ${student.classification.toLowerCase().replaceAll(' ', '-')}`}>{student.classification}</span><h2>{student.full_name}</h2><small>{student.student_id} · {student.batch} · {student.course}</small></div><strong>{student.metrics.completion_percentage}%<small>completion</small></strong></div><div className="risk-metrics"><span>{student.metrics.pending_tasks} pending</span><span>{student.metrics.overdue_tasks} overdue</span><span>{student.metrics.performance_average === null ? 'No scored tasks' : `${student.metrics.performance_average}% performance`}</span><span>{student.metrics.completion_trend} recent completion trend</span></div><ul>{student.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul><p className="risk-action"><b>Suggested action</b>{student.suggested_action}</p></article>)}</div>}
  </>
}

function BatchPage() {
  const { data: batches, loading, error } = useResource<Batch[]>('/api/v1/admin/batches')
  const [selectedOverride, setSelectedOverride] = useState('')
  const selected = selectedOverride || batches?.[0]?.batch || ''
  const [batch, setBatch] = useState<Batch | null>(null)
  const [insight, setInsight] = useState<{ summary: string; learning_trends: string[]; recommendations: string[] } | null>(null)
  const [failure, setFailure] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    if (!selected) return
    let mounted = true
    request<Batch>(`/api/v1/admin/batches/${encodeURIComponent(selected)}`)
      .then((result) => { if (mounted) setBatch(result) })
      .catch((requestError) => { if (mounted) setFailure(requestError instanceof Error ? requestError.message : 'Batch unavailable.') })
    return () => { mounted = false }
  }, [selected])
  async function analyze() {
    setBusy(true); setFailure('')
    try { setInsight(await request<{ summary: string; learning_trends: string[]; recommendations: string[] }>(`/api/v1/admin/batches/${encodeURIComponent(selected)}/insights`, { method: 'POST' })) }
    catch (requestError) { setFailure(requestError instanceof Error ? requestError.message : 'AI batch insight unavailable.') }
    finally { setBusy(false) }
  }
  return <>
    <PageHeader eyebrow="FEATURE 05 · BATCH INTELLIGENCE" title="Batch intelligence" description="Explore cohort progress, topic mastery, task difficulty, and support signals." action={<select value={selected} onChange={(e) => { setSelectedOverride(e.target.value); setBatch(null); setInsight(null) }} aria-label="Select batch">{(batches ?? []).map((item) => <option key={item.batch}>{item.batch}</option>)}</select>} />
    {loading && <Notice>Loading batch records…</Notice>}{error && <Notice kind="error">{error}</Notice>}{failure && <Notice kind="error">{failure}</Notice>}
    {!loading && !batches?.length && <EmptyState text="No active batches are available." />}
    {batch && <>
      <div className="profile-metrics"><Metric label="Students" value={batch.student_count} detail={batch.batch} /><Metric label="Average completion" value={`${batch.average_completion}%`} detail="Mean per-student completion" /><Metric label="Average performance" value={batch.average_performance === null ? '—' : `${batch.average_performance}%`} detail="Recorded task scores" /><Metric label="Pending / overdue" value={`${batch.pending_tasks} / ${batch.overdue_tasks}`} detail="Assignments needing action" /></div>
      <div className="admin-dashboard-columns"><section className="admin-panel-card"><div className="section-heading"><div><p className="admin-eyebrow">TOPIC SIGNALS</p><h2>Recorded mastery</h2></div></div>
        {!batch.topic_mastery.length ? <EmptyState text="No topic mastery records for this batch." /> : batch.topic_mastery.map((topic) => <div className="mastery-row" key={topic.topic}><div><span>{topic.topic}<small>{topic.student_count} student records</small></span><b>{topic.average_mastery}%</b></div><div className="mastery-track"><i style={{ width: `${topic.average_mastery}%` }} /></div></div>)}
        <div className="topic-labels"><span><b>Strong:</b> {batch.strong_topics.map((item) => item.topic).join(', ') || 'No topic average at or above 80% yet'}</span><span><b>Needs support:</b> {batch.weak_topics.map((item) => item.topic).join(', ') || 'No topic average below 65%'}</span></div>
      </section><section className="admin-panel-card"><div className="section-heading"><div><p className="admin-eyebrow">TASK DESIGN</p><h2>Difficulty patterns</h2></div></div>
        {!batch.difficulty_patterns.length ? <EmptyState text="No task difficulty data recorded." /> : <div className="difficulty-list">{batch.difficulty_patterns.map((item) => <div key={item.difficulty}><strong>{item.difficulty}</strong><span>{item.completed}/{item.assignments} complete</span><b>{item.average_performance === null ? '—' : `${item.average_performance}%`}</b></div>)}</div>}
        <div className="section-heading support-heading"><div><p className="admin-eyebrow">SUPPORT SIGNALS</p><h2>Students to check in with</h2></div></div>
        {!batch.students_needing_support.length ? <EmptyState text="No students are currently flagged by deterministic risk rules." /> : batch.students_needing_support.map((student) => <div className="support-student" key={student.student_id}><span>{student.full_name}<small>{student.student_id}</small></span><b>{student.classification}</b></div>)}
      </section></div>
      <section className="admin-panel-card"><div className="section-heading"><div><p className="admin-eyebrow">RECENT WEEKS</p><h2>Assignment completion trend</h2></div></div>{!batch.weekly_trend.length ? <EmptyState text="Not enough dated assignments to chart." /> : <div className="trend-bars" role="img" aria-label="Weekly assigned and completed task counts">{[...batch.weekly_trend].reverse().map((week) => <div key={week.week}><span>{week.week ?? 'Unknown'}</span><div className="trend-bar"><i style={{ height: `${Math.min(100, (week.assigned ? week.completed / week.assigned : 0) * 100)}%` }} /></div><small>{week.completed}/{week.assigned}</small></div>)}</div>}</section>
      <section className="ai-insight-card"><div className="ai-orb">✦</div><div className="ai-insight-content"><p className="admin-eyebrow">GROQ · RECORDED BATCH DATA</p><h2>Learning trends & recommendations</h2>{insight && <><p>{insight.summary}</p><div className="ai-insight-detail"><span><b>Trends</b>{insight.learning_trends.join(' · ') || 'No supported trend found'}</span><span><b>Recommended actions</b>{insight.recommendations.join(' · ') || 'No recommendations returned'}</span></div></>}</div><button className="admin-button primary" disabled={busy} onClick={analyze}>{busy ? 'Analyzing…' : 'Generate batch insight'}</button></section>
    </>}
  </>
}

function CopilotReportsPage() {
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<{ answer: string; supporting_data: string[] } | null>(null)
  const [failure, setFailure] = useState('')
  const [busy, setBusy] = useState(false)
  const { data: reports, loading, error, refresh } = useResource<Report[]>('/api/v1/admin/reports')
  const [reportType, setReportType] = useState('weekly')
  const [studentId, setStudentId] = useState('')
  const [batchName, setBatchName] = useState('')
  const [reportBusy, setReportBusy] = useState(false)
  const { data: reportStudents } = useResource<Student[]>('/api/v1/admin/students?active=true')
  const { data: reportBatches } = useResource<Batch[]>('/api/v1/admin/batches')

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setFailure(''); setAnswer(null)
    try { setAnswer(await request<{ answer: string; supporting_data: string[] }>('/api/v1/admin/copilot', { method: 'POST', body: JSON.stringify({ question }) })) }
    catch (requestError) { setFailure(requestError instanceof Error ? requestError.message : 'Copilot unavailable.') }
    finally { setBusy(false) }
  }
  async function generateReport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setReportBusy(true); setFailure('')
    const payload: { report_type: string; student_id?: number; batch?: string } = { report_type: reportType }
    if (reportType === 'student') payload.student_id = Number(studentId)
    if (reportType === 'batch') payload.batch = batchName
    try {
      await request('/api/v1/admin/reports', { method: 'POST', body: JSON.stringify(payload) })
      setFailure('Report generated and saved.')
      void refresh()
    } catch (requestError) { setFailure(requestError instanceof Error ? requestError.message : 'Report generation unavailable.') }
    finally { setReportBusy(false) }
  }

  return <>
    <PageHeader eyebrow="FEATURE 06 · ADMIN COPILOT & REPORTS" title="Ask the academy data" description="Query actual records or create a saved report. Groq receives scoped database context, never direct database access." />
    <div className="copilot-grid"><section className="admin-panel-card copilot-card"><p className="admin-eyebrow">GROQ · GROUNDED ANSWERS</p><h2>What would you like to know?</h2><p>Try overdue students, highest performance, learners needing attention, weekly summary, or the best-performing batch.</p>
      <form className="copilot-form" onSubmit={ask}><label htmlFor="copilot-question">Question</label><textarea id="copilot-question" value={question} onChange={(e) => setQuestion(e.target.value)} minLength={3} maxLength={1000} required rows={3} placeholder="Who has overdue tasks?" /><button className="admin-button primary" disabled={busy}>{busy ? 'Looking up records…' : 'Ask Copilot'}</button></form>
      {failure && <Notice kind={failure.startsWith('Report generated') ? 'success' : 'error'}>{failure}</Notice>}
      {answer && <div className="copilot-answer"><p>{answer.answer}</p>{answer.supporting_data.length > 0 && <><b>Supporting records</b><ul>{answer.supporting_data.map((item) => <li key={item}>{item}</li>)}</ul></>}</div>}
    </section>
      <section className="admin-panel-card report-builder"><p className="admin-eyebrow">SMART REPORTS</p><h2>Generate a report</h2><p>Reports include backend-calculated metrics and Groq interpretation of the same records.</p>
        <form className="admin-form" onSubmit={generateReport}><label>Report type<select value={reportType} onChange={(e) => setReportType(e.target.value)}><option value="weekly">Weekly summary</option><option value="performance">Performance report</option><option value="student">Student report</option><option value="batch">Batch report</option></select></label>
          {reportType === 'student' && <label>Student<select required value={studentId} onChange={(e) => setStudentId(e.target.value)}><option value="">Choose a student</option>{(reportStudents ?? []).map((student) => <option key={student.id} value={student.id}>{student.full_name} · {student.student_id}</option>)}</select></label>}
          {reportType === 'batch' && <label>Batch<select required value={batchName} onChange={(e) => setBatchName(e.target.value)}><option value="">Choose a batch</option>{(reportBatches ?? []).map((batch) => <option key={batch.batch}>{batch.batch}</option>)}</select></label>}
          <button className="admin-button primary" disabled={reportBusy}>{reportBusy ? 'Generating…' : 'Generate & save report'}</button>
        </form><p className="form-help">AI reports need Groq configured. Unconfigured requests are not saved as successful reports.</p>
      </section>
    </div>
    <section className="admin-panel-card reports-list"><div className="section-heading"><div><p className="admin-eyebrow">SAVED OUTPUTS</p><h2>Reports</h2></div></div>
      {loading && <Notice>Loading reports…</Notice>}{error && <Notice kind="error">{error}</Notice>}{reports && !reports.length && <EmptyState text="No reports have been generated yet." />}
      {reports && reports.length > 0 && reports.map((report) => <details className="saved-report" key={report.id}><summary><span>{report.content.ai_analysis?.title ?? `${report.report_type} report`}</span><small>{report.report_type} · {report.full_name ?? 'Academy'} · {new Date(`${report.created_at.replace(' ', 'T')}Z`).toLocaleString()}</small></summary><p>{report.content.ai_analysis?.summary ?? 'Report detail unavailable.'}</p><ul>{report.content.ai_analysis?.insights.map((item) => <li key={item}>{item}</li>)}</ul></details>)}
    </section>
  </>
}

export default function AdminPanel() {
  return <Routes><Route element={<AdminLayout />}><Route index element={<DashboardPage />} /><Route path="students" element={<StudentsPage />} /><Route path="students/:studentId" element={<StudentProfilePage />} /><Route path="tasks" element={<TaskStudioPage />} /><Route path="performance" element={<PerformancePage />} /><Route path="batches" element={<BatchPage />} /><Route path="copilot" element={<CopilotReportsPage />} /><Route path="*" element={<DashboardPage />} /></Route></Routes>
}
