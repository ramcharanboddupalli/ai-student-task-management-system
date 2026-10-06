import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { ApiError, request } from './services/api'
import StudentAISection from './StudentAISections'
import './StudentPanel.css'

type Student = {
  id: number
  student_id: string
  full_name: string
  course: string
  batch: string
  current_level: string
}

type StudentTask = {
  assignment_id: number
  title: string
  description: string
  topic: string
  course: string
  difficulty: string
  priority: string
  estimated_minutes: number
  status: 'Pending' | 'In Progress' | 'Completed'
  deadline: string
  performance_score: number | null
  reason?: string
  rationale?: string
}

type Dashboard = {
  student: Student
  total_tasks: number
  completed_tasks: number
  pending_tasks: number
  in_progress_tasks: number
  overdue_tasks: number
  completion_percentage: number
  today_priority: StudentTask | null
  upcoming_deadlines: StudentTask[]
}

type DailyInsight = {
  headline: string
  summary: string
  recommended_action: string
}

type Prioritization = {
  recommendations: StudentTask[]
  message?: string
}

function StudentPanel() {
  const [student, setStudent] = useState<Student | null>(null)
  const [loading, setLoading] = useState(true)
  const [sessionError, setSessionError] = useState('')
  const [logoutError, setLogoutError] = useState('')
  const [navOpen, setNavOpen] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    let active = true
    request<Student & { role: string }>('/api/v1/auth/me')
      .then((user) => {
        if (!active) return
        if (user.role !== 'student') {
          navigate('/admin', { replace: true })
          return
        }
        setStudent(user)
      })
      .catch((error: unknown) => {
        if (!active) return
        if (error instanceof ApiError && error.status === 401) {
          navigate('/student/login', { replace: true })
        } else {
          setSessionError(error instanceof Error ? error.message : 'Unable to verify your session.')
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [navigate])

  async function signOut() {
    setLogoutError('')
    try {
      await request('/api/v1/auth/logout', { method: 'POST' })
      navigate('/student/login', { replace: true })
    } catch (error) {
      setLogoutError(error instanceof Error ? error.message : 'Unable to sign out.')
    }
  }

  if (loading) return <div className="student-loading" role="status">Checking your secure student session…</div>
  if (sessionError) return <div className="student-loading student-error" role="alert">{sessionError}</div>
  if (!student) return null

  const isTasksPage = location.pathname.endsWith('/tasks')
  const isDashboardPage = location.pathname === '/student' || location.pathname === '/student/dashboard'
  return (
    <div className={`student-app${navOpen ? ' nav-open' : ''}`}>
      <aside className="student-sidebar">
        <Link className="student-brand" to="/student/dashboard" aria-label="Skillonex student dashboard">
          <span className="student-brand-mark">S</span>
          <span>Skillonex <small>LEARNING SPACE</small></span>
        </Link>
        <p className="student-nav-caption">YOUR LEARNING</p>
        <nav className="student-nav" aria-label="Student navigation">
          <NavLink to="/student/dashboard" onClick={() => setNavOpen(false)}><span className="student-nav-icon">01</span><span>Dashboard<small>Progress at a glance</small></span></NavLink>
          <NavLink to="/student/tasks" onClick={() => setNavOpen(false)}><span className="student-nav-icon">02</span><span>Smart Task Center<small>Assigned tasks</small></span></NavLink>
          <NavLink to="/student/assistant" onClick={() => setNavOpen(false)}><span className="student-nav-icon">03</span><span>Personal AI Assistant<small>Personal learning tutor</small></span></NavLink>
          <NavLink to="/student/coach" onClick={() => setNavOpen(false)}><span className="student-nav-icon">04</span><span>Learning Coach<small>Progress & next steps</small></span></NavLink>
          <NavLink to="/student/planner" onClick={() => setNavOpen(false)}><span className="student-nav-icon">05</span><span>Study Planner<small>Plan your study time</small></span></NavLink>
          <NavLink to="/student/practice" onClick={() => setNavOpen(false)}><span className="student-nav-icon">06</span><span>Practice & Skill Builder<small>Build topic mastery</small></span></NavLink>
          <NavLink to="/student/report" onClick={() => setNavOpen(false)}><span className="student-nav-icon">07</span><span>Progress & Career Report<small>Learning & career view</small></span></NavLink>
        </nav>
        <div className="student-sidebar-bottom">
          <div className="student-user">
            <span aria-hidden="true">{student.full_name.trim().charAt(0).toUpperCase()}</span>
            <div><strong>{student.full_name}</strong><small>{student.student_id}</small></div>
          </div>
          <button className="student-signout" onClick={signOut}>Sign out <span aria-hidden="true">↗</span></button>
        </div>
      </aside>
      {navOpen && <button className="student-mobile-backdrop" type="button" aria-label="Close navigation" onClick={() => setNavOpen(false)} />}
      <main className="student-main">
        <header className="student-topbar">
          <button className="student-menu-toggle" type="button" aria-label="Open navigation" aria-expanded={navOpen} onClick={() => setNavOpen(true)}>☰</button>
          <span className="student-breadcrumb">Skillonex Academy <b>/</b> Learning space</span>
          <span className="student-online"><i aria-hidden="true" /> Private student workspace</span>
        </header>
        {logoutError && <p className="student-notice error student-logout-error" role="alert">{logoutError}</p>}
        {isTasksPage ? <TaskCenter /> : isDashboardPage ? <StudentDashboard /> : (
          <StudentAISection path={location.pathname} />
        )}
      </main>
    </div>
  )
}

function StudentDashboard() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [tasks, setTasks] = useState<StudentTask[]>([])
  const [insight, setInsight] = useState<DailyInsight | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [quickTaskError, setQuickTaskError] = useState('')
  const [taskUpdate, setTaskUpdate] = useState<number | null>(null)
  const [taskUpdateNotice, setTaskUpdateNotice] = useState('')
  const [prioritizedTasks, setPrioritizedTasks] = useState<StudentTask[] | null>(null)
  const [prioritizationMessage, setPrioritizationMessage] = useState('')
  const [prioritizationError, setPrioritizationError] = useState('')
  const [prioritizationLoading, setPrioritizationLoading] = useState(false)
  const [insightError, setInsightError] = useState('')
  const [insightLoading, setInsightLoading] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    let active = true
    Promise.allSettled([
      request<Dashboard>('/api/v1/student/dashboard'),
      request<StudentTask[]>('/api/v1/student/tasks'),
    ])
      .then(([dashboardResult, tasksResult]) => {
        if (!active) return
        if (dashboardResult.status === 'rejected') {
          const requestError = dashboardResult.reason as unknown
          if (requestError instanceof ApiError && requestError.status === 401) {
            navigate('/student/login', { replace: true })
            return
          }
          setError(requestError instanceof Error ? requestError.message : 'Unable to load your dashboard.')
          return
        }
        setDashboard(dashboardResult.value)
        if (tasksResult.status === 'fulfilled') {
          setTasks(tasksResult.value)
        } else if (tasksResult.reason instanceof ApiError && tasksResult.reason.status === 401) {
          navigate('/student/login', { replace: true })
        } else {
          setQuickTaskError(tasksResult.reason instanceof Error ? tasksResult.reason.message : 'Unable to load your tasks.')
        }
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [navigate])

  async function updateQuickTask(task: StudentTask) {
    const nextStatus = task.status === 'Pending' ? 'In Progress' : 'Completed'
    setTaskUpdate(task.assignment_id)
    setTaskUpdateNotice('')
    setQuickTaskError('')
    try {
      const updated = await request<StudentTask>(`/api/v1/student/tasks/${task.assignment_id}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status: nextStatus }),
      })
      setTasks((current) => current.map((item) => item.assignment_id === updated.assignment_id ? updated : item))
      setTaskUpdateNotice(`“${task.title}” marked ${nextStatus.toLowerCase()}.`)
      const [updatedTasks, updatedDashboard] = await Promise.allSettled([
        request<StudentTask[]>('/api/v1/student/tasks'),
        request<Dashboard>('/api/v1/student/dashboard'),
      ])
      if (updatedTasks.status === 'fulfilled') setTasks(updatedTasks.value)
      if (updatedDashboard.status === 'fulfilled') setDashboard(updatedDashboard.value)
      else setQuickTaskError('Task updated, but the dashboard could not be refreshed. Reload the page to see current totals.')
    } catch (requestError) {
      setQuickTaskError(requestError instanceof Error ? requestError.message : 'Unable to update this task.')
    } finally {
      setTaskUpdate(null)
    }
  }

  async function prioritizeDashboardTasks() {
    setPrioritizationLoading(true)
    setPrioritizationError('')
    setPrioritizationMessage('')
    try {
      const result = await request<Prioritization>('/api/v1/student/tasks/prioritization', { method: 'POST' })
      setPrioritizedTasks(result.recommendations)
      setPrioritizationMessage(result.message ?? '')
    } catch (requestError) {
      setPrioritizationError(requestError instanceof Error ? requestError.message : 'Task prioritization is unavailable.')
    } finally {
      setPrioritizationLoading(false)
    }
  }

  async function loadInsight() {
    setInsightLoading(true)
    setInsightError('')
    try {
      setInsight(await request<DailyInsight>('/api/v1/student/insights/daily'))
    } catch (requestError) {
      setInsightError(requestError instanceof Error ? requestError.message : 'Daily insight is unavailable.')
    } finally {
      setInsightLoading(false)
    }
  }

  if (loading) return <div className="student-state" role="status">Loading your learning dashboard…</div>
  if (error) return <div className="student-state student-error" role="alert">{error}</div>
  if (!dashboard) return <div className="student-state">Your dashboard is not available.</div>

  const metrics = [
    { label: 'Assigned', value: dashboard.total_tasks, detail: 'Tasks in your queue' },
    { label: 'Completed', value: dashboard.completed_tasks, detail: 'Tasks finished' },
    { label: 'In progress', value: dashboard.in_progress_tasks, detail: 'Work underway' },
    { label: 'Pending', value: dashboard.pending_tasks, detail: 'Ready to begin' },
    { label: 'Overdue', value: dashboard.overdue_tasks, detail: 'Past due date', alert: dashboard.overdue_tasks > 0 },
  ]
  const openTasks = tasks.filter((task) => task.status !== 'Completed')
  const quickTasks = [...openTasks].sort((a, b) => {
    const aOverdue = isOverdue(a.deadline)
    const bOverdue = isOverdue(b.deadline)
    if (aOverdue !== bOverdue) return aOverdue ? -1 : 1
    return a.deadline.localeCompare(b.deadline)
  }).slice(0, 3)

  return (
    <div className="student-content">
      <section className="student-welcome">
        <div>
          <p className="student-eyebrow"><span className="student-spark" /> YOUR LEARNING DASHBOARD</p>
          <h1>{timeGreeting()}, {dashboard.student.full_name.split(' ')[0]}.</h1>
          <p>Your learning snapshot, grounded in your assigned work and recorded progress.</p>
          <div className="student-course-line">
            <span>{dashboard.student.course}</span><i aria-hidden="true">·</i>
            <span>{dashboard.student.batch}</span><i aria-hidden="true">·</i>
            <strong>{dashboard.student.current_level} level</strong>
          </div>
        </div>
        <div className="student-progress-ring" style={{ background: `conic-gradient(var(--lime-ink) ${dashboard.completion_percentage}%, var(--ring-track) 0)` }} role="progressbar" aria-label="Task completion" aria-valuemin={0} aria-valuemax={100} aria-valuenow={dashboard.completion_percentage}>
          <div><strong>{dashboard.completion_percentage}%</strong><span>complete</span></div>
        </div>
      </section>

      <section className="student-metric-grid" aria-label="Personal progress">
        {metrics.map((metric) => (
          <article className={`student-metric${metric.alert ? ' alert' : ''}`} key={metric.label}>
            <span className="student-metric-label">{metric.label}</span>
            <strong>{metric.value}</strong>
            <small>{metric.detail}</small>
          </article>
        ))}
      </section>

      <section className="student-card progress-overview" aria-labelledby="progress-overview-title">
        <div className="student-section-heading">
          <div><p className="student-eyebrow">CURRENT ASSIGNMENTS</p><h2 id="progress-overview-title">Progress overview</h2></div>
          <span className="student-progress-summary">{dashboard.completion_percentage}% complete</span>
        </div>
        <div className="student-stacked-progress" role="img" aria-label={`${dashboard.completed_tasks} completed, ${dashboard.in_progress_tasks} in progress, ${dashboard.pending_tasks} pending`}>
          <span className="progress-complete" style={{ width: `${dashboard.total_tasks ? dashboard.completed_tasks / dashboard.total_tasks * 100 : 0}%` }} />
          <span className="progress-active" style={{ width: `${dashboard.total_tasks ? dashboard.in_progress_tasks / dashboard.total_tasks * 100 : 0}%` }} />
          <span className="progress-pending" style={{ width: `${dashboard.total_tasks ? dashboard.pending_tasks / dashboard.total_tasks * 100 : 0}%` }} />
        </div>
        <div className="student-progress-legend">
          <span><i className="legend-complete" />Completed <b>{dashboard.completed_tasks}</b></span>
          <span><i className="legend-active" />In progress <b>{dashboard.in_progress_tasks}</b></span>
          <span><i className="legend-pending" />Pending <b>{dashboard.pending_tasks}</b></span>
          <span className={dashboard.overdue_tasks ? 'legend-overdue' : ''}><i className="legend-overdue-dot" />Overdue <b>{dashboard.overdue_tasks}</b></span>
        </div>
        {!dashboard.total_tasks && <p className="student-progress-empty">Progress will appear when tasks are assigned to you.</p>}
      </section>

      <div className="student-dashboard-grid">
        <section className="student-card priority-card">
          <div className="student-section-heading">
            <div><p className="student-eyebrow">YOUR NEXT BEST STEP</p><h2>Today's priority</h2></div>
            <span className="student-section-icon" aria-hidden="true">↗</span>
          </div>
          {dashboard.today_priority ? (
            <div className="today-task">
              <div className="today-task-top">
                <span className={`task-priority priority-${dashboard.today_priority.priority.toLowerCase()}`}>
                  {dashboard.today_priority.priority} priority
                </span>
                <span className="task-status">{dashboard.today_priority.status}</span>
              </div>
              <h3>{dashboard.today_priority.title}</h3>
              <p>{dashboard.today_priority.reason || dashboard.today_priority.description}</p>
              <div className="today-task-meta">
                <span className={isOverdue(dashboard.today_priority.deadline) ? 'overdue-date' : ''}>{isOverdue(dashboard.today_priority.deadline) ? 'Overdue' : 'Due'} {formatDate(dashboard.today_priority.deadline)}</span>
                <span>{dashboard.today_priority.difficulty}</span>
                <span>{dashboard.today_priority.estimated_minutes} min</span>
              </div>
              <Link className="student-text-link" to="/student/tasks">Open task center <span aria-hidden="true">↗</span></Link>
            </div>
          ) : (
            <div className="student-empty"><strong>Clear runway.</strong><p>You have no outstanding tasks to prioritize right now.</p></div>
          )}
        </section>

        <section className="student-card deadlines-card">
          <div className="student-section-heading">
            <div><p className="student-eyebrow">PLAN AHEAD</p><h2>Upcoming deadlines</h2></div>
            <Link to="/student/tasks" aria-label="View all tasks">View all ↗</Link>
          </div>
          {dashboard.upcoming_deadlines.length ? (
            <ul className="deadline-list">
              {dashboard.upcoming_deadlines.map((task) => (
                <li className={isOverdue(task.deadline) ? 'deadline-overdue' : ''} key={task.assignment_id}>
                  <span className="deadline-date"><strong>{datePart(task.deadline, 'day')}</strong><small>{datePart(task.deadline, 'month')}</small></span>
                  <div><strong>{task.title}</strong><small>{task.topic} · {task.status} · {task.estimated_minutes} min</small></div>
                  <span className={`deadline-priority priority-${task.priority.toLowerCase()}`}>{isOverdue(task.deadline) ? 'Overdue' : task.priority}</span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="student-empty"><strong>No upcoming deadlines.</strong><p>Completed work and overdue items stay available in your task center.</p></div>
          )}
        </section>
      </div>

      <section className="student-card quick-task-card" aria-labelledby="quick-task-title">
        <div className="student-section-heading">
          <div><p className="student-eyebrow">KEEP YOUR MOMENTUM</p><h2 id="quick-task-title">Quick task view</h2></div>
          <Link to="/student/tasks">All tasks ↗</Link>
        </div>
        {taskUpdateNotice && <p className="student-notice success" role="status">{taskUpdateNotice}</p>}
        {quickTaskError && <p className="student-notice error" role="alert">{quickTaskError}</p>}
        {quickTaskError && !tasks.length ? <div className="student-empty"><strong>Tasks could not be loaded.</strong><p>{quickTaskError}</p></div>
          : quickTasks.length ? <div className="quick-task-list">{quickTasks.map((task) => (
            <article className="quick-task-row" key={task.assignment_id}>
              <div className="quick-task-copy"><div className="student-task-tags"><span className={`task-status status-${task.status.toLowerCase().replace(' ', '-')}`}>{task.status}</span><span className={`task-priority priority-${task.priority.toLowerCase()}`}>{task.priority} priority</span></div><h3>{task.title}</h3><p>{task.topic} · {isOverdue(task.deadline) ? 'Overdue' : `Due ${formatDate(task.deadline)}`} · {task.estimated_minutes} min</p></div>
              <button className="student-button student-button-secondary" onClick={() => updateQuickTask(task)} disabled={taskUpdate === task.assignment_id}>{taskUpdate === task.assignment_id ? 'Saving…' : task.status === 'Pending' ? 'Start' : 'Complete'}</button>
            </article>
          ))}</div>
          : <div className="student-empty"><strong>Nothing needs attention right now.</strong><p>When an administrator assigns work, your tasks will appear here.</p></div>}
      </section>

      <section className="student-card dashboard-prioritization" aria-labelledby="dashboard-prioritization-title">
        <div className="student-section-heading">
          <div><p className="student-eyebrow">AI STUDY SUPPORT</p><h2 id="dashboard-prioritization-title">AI Task Prioritization</h2></div>
          <button className="student-button student-button-secondary" onClick={prioritizeDashboardTasks} disabled={prioritizationLoading || !openTasks.length}>
            {prioritizationLoading ? 'Reviewing your tasks…' : prioritizedTasks ? 'Refresh order' : 'Recommend task order'}
          </button>
        </div>
        <p className="student-prioritization-description">Get an advisory order based on your assigned deadlines, priority, difficulty, estimated time, and status. Recommendations never change task status.</p>
        {prioritizationError && <p className="student-notice error" role="alert">{prioritizationError}</p>}
        {prioritizationMessage && <p className="student-notice" role="status">{prioritizationMessage}</p>}
        {prioritizedTasks && prioritizedTasks.length > 0 && <ol className="dashboard-priority-list">{prioritizedTasks.map((task, index) => (
          <li key={task.assignment_id}>
            <span className="dashboard-priority-rank">{String(index + 1).padStart(2, '0')}</span>
            <div><strong>{task.title}</strong><small>{task.status} · {task.priority} priority · {isOverdue(task.deadline) ? 'Overdue' : `Due ${formatDate(task.deadline)}`} · {task.estimated_minutes} min</small><p>{task.rationale}</p></div>
          </li>
        ))}</ol>}
        {prioritizedTasks && !prioritizedTasks.length && !prioritizationMessage && <p className="student-prioritization-description">There are no outstanding assigned tasks to prioritize.</p>}
      </section>

      <section className="student-ai-card" aria-labelledby="daily-insight-title">
        <div className="student-ai-icon" aria-hidden="true">✦</div>
        <div className="student-ai-copy">
          <p className="student-eyebrow">PERSONALIZED · GROUNDED IN YOUR RECORDS</p>
          <h2 id="daily-insight-title">AI Daily Insight</h2>
          {insight ? (
            <div className="student-ai-result">
              <h3>{insight.headline}</h3><p>{insight.summary}</p>
              <div><strong>Recommended next step</strong><p>{insight.recommended_action}</p></div>
            </div>
          ) : (
            <p className="student-ai-description">A brief reflection on your recorded progress and what to focus on next.</p>
          )}
          {insightError && <p className="student-inline-error" role="alert">{insightError}</p>}
        </div>
        {!insight && (
          <button className="student-button student-button-light" onClick={loadInsight} disabled={insightLoading}>
            {insightLoading ? 'Reflecting…' : 'Generate insight'}
          </button>
        )}
      </section>
    </div>
  )
}

function timeGreeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

function TaskCenter() {
  const [tasks, setTasks] = useState<StudentTask[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [updating, setUpdating] = useState<number | null>(null)
  const [recommendations, setRecommendations] = useState<StudentTask[] | null>(null)
  const [priorityMessage, setPriorityMessage] = useState('')
  const [priorityError, setPriorityError] = useState('')
  const [priorityLoading, setPriorityLoading] = useState(false)
  const [statusFilter, setStatusFilter] = useState<'All' | StudentTask['status']>('All')
  const navigate = useNavigate()

  useEffect(() => {
    let active = true
    request<StudentTask[]>('/api/v1/student/tasks')
      .then((data) => { if (active) setTasks(data) })
      .catch((requestError: unknown) => {
        if (!active) return
        if (requestError instanceof ApiError && requestError.status === 401) {
          navigate('/student/login', { replace: true })
        } else {
          setError(requestError instanceof Error ? requestError.message : 'Unable to load your tasks.')
        }
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [navigate])

  async function updateStatus(task: StudentTask) {
    const nextStatus = task.status === 'Pending' ? 'In Progress' : 'Completed'
    setUpdating(task.assignment_id)
    setError('')
    setSuccess('')
    try {
      const updated = await request<StudentTask>(`/api/v1/student/tasks/${task.assignment_id}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status: nextStatus }),
      })
      setTasks((current) => current.map((item) => item.assignment_id === updated.assignment_id ? updated : item))
      setRecommendations(null)
      setPriorityMessage('')
      setSuccess(`“${updated.title}” marked ${updated.status.toLowerCase()}.`)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to update this task.')
    } finally {
      setUpdating(null)
    }
  }

  async function prioritize() {
    setPriorityLoading(true)
    setPriorityError('')
    setPriorityMessage('')
    try {
      const result = await request<Prioritization>('/api/v1/student/tasks/prioritization', { method: 'POST' })
      setRecommendations(result.recommendations)
      setPriorityMessage(result.message ?? '')
    } catch (requestError) {
      setPriorityError(requestError instanceof Error ? requestError.message : 'Task prioritization is unavailable.')
    } finally {
      setPriorityLoading(false)
    }
  }

  const displayTasks = recommendations
    ? [
        ...recommendations,
        ...tasks.filter((task) => task.status === 'Completed'),
      ]
    : tasks
  const filteredTasks = displayTasks.filter((task) => statusFilter === 'All' || task.status === statusFilter)

  return (
    <div className="student-content task-center">
      <div className="student-page-heading">
        <div><p className="student-eyebrow"><span className="student-spark" /> YOUR PERSONAL WORKSPACE</p>
          <h1>Smart Task Center</h1>
          <p>Your assignments, deadlines, and next actions in one place. AI recommendations are advisory and never change task status.</p>
        </div>
        <button className="student-button student-button-primary" onClick={prioritize} disabled={priorityLoading}>
          {priorityLoading ? 'Reviewing your tasks…' : '✦ Prioritize my tasks'}
        </button>
      </div>
      {error && <p className="student-notice error" role="alert">{error}</p>}
      {success && <p className="student-notice success" role="status">{success}</p>}
      {priorityError && <p className="student-notice error" role="alert">{priorityError}</p>}
      {priorityMessage && <p className="student-notice success" role="status">{priorityMessage}</p>}
      {recommendations && recommendations.length > 0 && <div className="student-priority-note" role="status">AI attention order is based on your real task details. Recommendations do not change task status.</div>}
      {!loading && !!tasks.length && <div className="task-list-toolbar" aria-label="Filter tasks by status">
        <div className="task-filter-group">{(['All', 'Pending', 'In Progress', 'Completed'] as const).map((status) => (
          <button key={status} className={statusFilter === status ? 'active' : ''} onClick={() => setStatusFilter(status)} aria-pressed={statusFilter === status}>{status}</button>
        ))}</div>
        <span>{filteredTasks.length} {filteredTasks.length === 1 ? 'task' : 'tasks'}</span>
      </div>}
      {loading ? <div className="student-state" role="status">Loading your assigned tasks…</div>
        : error && !tasks.length ? null
          : !tasks.length ? (
            <section className="student-card student-empty task-empty">
              <span className="student-empty-mark" aria-hidden="true">✦</span>
              <h2>Your task list is clear.</h2>
              <p>When your administrator assigns a task, it will appear here.</p>
            </section>
          ) : (
            filteredTasks.length ? <div className="student-task-list">
              {filteredTasks.map((task, index) => (
                <article className={`student-task-card${task.status === 'Completed' ? ' is-complete' : ''}`} key={task.assignment_id}>
                  <div className="student-task-number">{String(index + 1).padStart(2, '0')}</div>
                  <div className="student-task-main">
                    <div className="student-task-heading">
                      <div><div className="student-task-tags">
                        <span className={`task-status status-${task.status.toLowerCase().replace(' ', '-')}`}>{task.status}</span>
                        {task.status !== 'Completed' && <span className={`task-priority priority-${task.priority.toLowerCase()}`}>{task.priority} priority</span>}
                        {task.status !== 'Completed' && isOverdue(task.deadline) && <span className="task-status status-overdue">Overdue</span>}
                      </div><h2>{task.title}</h2></div>
                      {task.status !== 'Completed' && (
                        <button className="student-button student-button-primary task-action" onClick={() => updateStatus(task)} disabled={updating === task.assignment_id}>
                          {updating === task.assignment_id ? 'Saving…' : task.status === 'Pending' ? 'Start task' : 'Mark completed'}
                        </button>
                      )}
                    </div>
                    <p className="student-task-description">{task.description}</p>
                    <div className="student-task-meta">
                      <span>{task.course} <i>·</i> {task.topic}</span>
                      <span>Difficulty: {task.difficulty}</span>
                      <span>Estimated: {task.estimated_minutes} min</span>
                      <span className={task.status !== 'Completed' && isOverdue(task.deadline) ? 'overdue-date' : ''}>
                        {task.status === 'Completed' ? 'Deadline' : isOverdue(task.deadline) ? 'Overdue' : 'Due'} {formatDate(task.deadline)}
                      </span>
                    </div>
                    {task.rationale && <p className="student-task-rationale"><strong>Why this order</strong>{task.rationale}</p>}
                  </div>
                </article>
              ))}
            </div> : <section className="student-card student-empty task-empty"><h2>No {statusFilter.toLowerCase()} tasks.</h2><p>Choose another status filter to see more of your assignments.</p></section>
          )}
    </div>
  )
}

function isOverdue(value: string) {
  const now = new Date()
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  return value < today
}

function formatDate(value: string) {
  const parsed = new Date(`${value}T00:00:00`)
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function datePart(value: string, part: 'day' | 'month') {
  const parsed = new Date(`${value}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) return part === 'day' ? '--' : '---'
  return part === 'day'
    ? new Intl.DateTimeFormat(undefined, { day: '2-digit' }).format(parsed)
    : new Intl.DateTimeFormat(undefined, { month: 'short' }).format(parsed).toUpperCase()
}

export default StudentPanel
