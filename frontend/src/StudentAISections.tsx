import { useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { request } from './services/api'
import './StudentAISections.css'

type PageProps = { path: string }
type TaskSummary = {
  assignment_id: number
  title: string
  topic: string
  status: string
  deadline: string
  difficulty: string
  estimated_minutes: number
  priority: string
}
type StudentSnapshot = {
  student: {
    full_name: string
    course: string
    batch: string
    current_level: string
  }
  total_tasks: number
  completed_tasks: number
  pending_tasks: number
  in_progress_tasks: number
  overdue_tasks: number
  completion_percentage: number
}
type ProgressMetrics = Omit<StudentSnapshot, 'student'> & {
  average_recorded_performance: number | null
}
type AssistantMessage = { role: 'user' | 'assistant'; content: string }
type CoachAnalysis = {
  strengths: string[]
  weak_areas: string[]
  learning_gaps: string[]
  progress_trend: string
  recommended_next_topic: string | null
  recommended_next_task: TaskSummary | null
  improvement_actions: string[]
  coaching_advice: string
  student: StudentSnapshot['student']
  metrics: ProgressMetrics
  analyzed_at: string
}
type PlannedSession = {
  assignment_id: number
  title: string
  topic: string
  study_date: string
  session_number: number
  minutes: number
  status: string
  deadline: string
  is_overdue: boolean
  priority: string
  reason: string
}
type StudyPlan = {
  generated_at: string
  today: string
  today_sessions: PlannedSession[]
  upcoming_sessions: PlannedSession[]
  unscheduled_tasks: Array<TaskSummary & { remaining_minutes: number }>
  priority_explanation: string
  study_advice: string
  message: string | null
}
type PracticeQuestion = {
  question_id: number
  question: string
  topic: string
  difficulty: string
  options: string[]
}
type PracticeSet = {
  practice_id: string
  topic: string
  difficulty: string
  practice_type: string
  question_count: number
  generated_at: string
  questions: PracticeQuestion[]
}
type PracticeResult = {
  score: number
  question_count: number
  correct_count: number
  weak_areas: string[]
  recommendation: string
  results: Array<{
    question_id: number
    question: string
    student_answer: string
    correct_answer: string
    explanation: string
    feedback: string
    score: number
    is_correct: boolean
    topic: string
  }>
}
type ProgressReport = {
  id: number
  report_type: string
  created_at: string
  content: {
    title: string
    report_date: string
    summary: string
    strengths: string[]
    weak_skills: string[]
    learning_gaps: string[]
    recommended_topics: string[]
    next_skills: string[]
    career_suggestions: string[]
    overall_recommendation: string
    metrics: {
      total_tasks: number
      completed_tasks: number
      in_progress_tasks: number
      pending_tasks: number
      overdue_tasks: number
      completion_percentage: number
      average_recorded_performance: number | null
      performance_category: string
    }
  }
}

const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const PRACTICE_TYPES = ['Multiple Choice', 'Short Answer', 'Mini Challenge', 'Revision Questions']
const DIFFICULTIES = ['Beginner', 'Intermediate', 'Advanced']

function messageFrom(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback
}

function SectionHeading({ eyebrow, title, detail }: { eyebrow: string; title: string; detail?: string }) {
  return (
    <div className="student-ai-heading">
      <p className="student-eyebrow"><span className="student-spark" /> {eyebrow}</p>
      <h1>{title}</h1>
      {detail && <p>{detail}</p>}
    </div>
  )
}

function Notice({ kind, children }: { kind: 'error' | 'success'; children: string }) {
  return <p className={`student-notice ${kind}`} role={kind === 'error' ? 'alert' : 'status'}>{children}</p>
}

function FeatureCard({ title, icon, children }: { title: string; icon: string; children: ReactNode }) {
  return (
    <section className="student-card ai-feature-card">
      <div className="ai-feature-card-heading"><span aria-hidden="true">{icon}</span><h2>{title}</h2></div>
      {children}
    </section>
  )
}

function AssistantPage() {
  const [snapshot, setSnapshot] = useState<StudentSnapshot | null>(null)
  const [messages, setMessages] = useState<AssistantMessage[]>([])
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [contextError, setContextError] = useState('')
  const [error, setError] = useState('')
  const suggestions = [
    'Explain my current task',
    'Explain this topic simply',
    'Give me an example',
    'What should I study next?',
    'Help me understand my weak areas',
  ]

  useEffect(() => {
    let active = true
    request<StudentSnapshot>('/api/v1/student/dashboard')
      .then((data) => { if (active) setSnapshot(data) })
      .catch((requestError: unknown) => {
        if (active) setContextError(messageFrom(requestError, 'Your learning context is unavailable.'))
      })
    return () => { active = false }
  }, [])

  async function sendMessage(event?: FormEvent, suggested?: string) {
    event?.preventDefault()
    const currentQuestion = (suggested ?? question).trim()
    if (!currentQuestion || loading) return
    setError('')
    setQuestion('')
    setMessages((current) => [...current, { role: 'user', content: currentQuestion }])
    setLoading(true)
    try {
      const response = await request<{ answer: string }>('/api/v1/student/assistant', {
        method: 'POST',
        body: JSON.stringify({
          question: currentQuestion,
          conversation: messages.slice(-10),
        }),
      })
      setMessages((current) => [...current, { role: 'assistant', content: response.answer }])
    } catch (requestError) {
      setError(messageFrom(requestError, 'The assistant could not respond. Please try again.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="student-content ai-feature-page assistant-page">
      <SectionHeading eyebrow="YOUR PERSONAL TUTOR" title="Personal AI Assistant" detail="Ask about your course, recorded skills, and assigned work. Answers use your own learning context." />
      <div className="assistant-layout">
        <FeatureCard title="Learning context" icon="◉">
          {contextError ? <Notice kind="error">{contextError}</Notice> : snapshot ? (
            <div className="assistant-context">
              <strong>{snapshot.student.course}</strong>
              <span>{snapshot.student.current_level} level · {snapshot.student.batch}</span>
              <span>{snapshot.completed_tasks} of {snapshot.total_tasks} assigned tasks completed</span>
              <span>{snapshot.pending_tasks} pending · {snapshot.in_progress_tasks} in progress · {snapshot.overdue_tasks} overdue</span>
            </div>
          ) : <p className="ai-muted" role="status">Loading your student context…</p>}
          <p className="ai-context-note">Your assistant is scoped to your authenticated student account.</p>
        </FeatureCard>
        <section className="student-card ai-feature-card assistant-chat" aria-label="Tutor conversation">
          <div className="ai-feature-card-heading">
            <span aria-hidden="true">✦</span><h2>Ask your learning tutor</h2>
            <button className="student-button student-button-secondary" type="button" onClick={() => { setMessages([]); setQuestion(''); setError('') }} disabled={loading || (!messages.length && !question)}>Clear</button>
          </div>
          <div className="assistant-messages" aria-live="polite">
            {!messages.length && <div className="assistant-welcome"><strong>What are you working through?</strong><p>Get an explanation grounded in your course and current assigned work.</p></div>}
            {messages.map((message, index) => (
              <article className={`assistant-message ${message.role}`} key={`${message.role}-${index}`}>
                <span>{message.role === 'assistant' ? 'LEARNING TUTOR' : 'YOU'}</span>
                <p>{message.content}</p>
              </article>
            ))}
            {loading && <p className="ai-loading" role="status">Thinking through your question…</p>}
          </div>
          {error && <Notice kind="error">{error}</Notice>}
          <div className="assistant-suggestions" aria-label="Suggested questions">
            {suggestions.map((suggestion) => (
              <button className="student-button student-button-secondary" key={suggestion} type="button" onClick={() => { setQuestion(suggestion); void sendMessage(undefined, suggestion) }} disabled={loading}>{suggestion}</button>
            ))}
          </div>
          <form className="assistant-compose" onSubmit={(event) => void sendMessage(event)}>
            <label htmlFor="assistant-question">Your question</label>
            <div><textarea id="assistant-question" value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={1200} rows={3} placeholder="Tell me what you would like help understanding…" required />
              <button className="student-button student-button-primary" type="submit" disabled={loading || !question.trim()}>{loading ? 'Sending…' : 'Send question'}</button>
            </div>
          </form>
        </section>
      </div>
    </div>
  )
}

function CoachPage() {
  const [analysis, setAnalysis] = useState<CoachAnalysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function refresh() {
    setLoading(true)
    setError('')
    try {
      setAnalysis(await request<CoachAnalysis>('/api/v1/student/coach', { method: 'POST' }))
    } catch (requestError) {
      setError(messageFrom(requestError, 'Your learning analysis could not be generated.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="student-content ai-feature-page">
      <div className="student-page-heading">
        <SectionHeading eyebrow="A CLEARER VIEW OF YOUR LEARNING" title="AI Learning Coach" detail="Understand the strengths, gaps, and next steps suggested by your recorded progress." />
        <button className="student-button student-button-primary" type="button" onClick={() => void refresh()} disabled={loading}>{loading ? 'Analyzing your records…' : analysis ? 'Refresh analysis' : 'Analyze my progress'}</button>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {!analysis && !loading && !error && <section className="student-card ai-empty-state"><span aria-hidden="true">✦</span><h2>Your coach is ready when you are.</h2><p>Generate an analysis to review your actual assignments, recorded skill levels, and progress.</p></section>}
      {loading && <div className="student-state" role="status">Reviewing your recorded learning progress…</div>}
      {analysis && (
        <>
          <div className="coach-summary student-welcome">
            <div><p className="student-eyebrow">CURRENT LEARNING LEVEL</p><h2>{analysis.student.current_level}</h2><p>{analysis.student.course} · {analysis.student.batch}</p></div>
            <div className="coach-completion"><strong>{analysis.metrics.completion_percentage}%</strong><span>completion</span><div className="student-stacked-progress"><i style={{ width: `${analysis.metrics.completion_percentage}%` }} /></div></div>
          </div>
          <p className="ai-last-analyzed">Last analyzed {new Date(analysis.analyzed_at).toLocaleString()}</p>
          <section className="ai-card-grid">
            <FeatureCard title="Your Strengths" icon="↗"><TagList values={analysis.strengths} empty="No specific strengths were identified from the available records yet." tone="positive" /></FeatureCard>
            <FeatureCard title="Weak Areas" icon="◎"><TagList values={analysis.weak_areas} empty="No specific weak areas were identified from the available records yet." tone="caution" /></FeatureCard>
            <FeatureCard title="Learning Gaps" icon="⌁"><TagList values={analysis.learning_gaps} empty="No learning gaps were identified from the available records yet." /></FeatureCard>
            <FeatureCard title="Progress Trend" icon="◷"><p className="ai-feature-copy">{analysis.progress_trend}</p></FeatureCard>
          </section>
          <FeatureCard title="Recommended Next Step" icon="➜">
            {analysis.recommended_next_task ? <div className="ai-recommended-task"><strong>{analysis.recommended_next_task.title}</strong><span>{analysis.recommended_next_task.topic} · {analysis.recommended_next_task.status} · due {formatDate(analysis.recommended_next_task.deadline)}</span></div> : <p className="ai-feature-copy">There is no outstanding assigned task to recommend.</p>}
            {analysis.recommended_next_topic && <p className="ai-feature-copy">Topic: <strong>{analysis.recommended_next_topic}</strong></p>}
            <TagList values={analysis.improvement_actions} empty="No additional action was suggested." />
          </FeatureCard>
          <FeatureCard title="AI Coaching Advice" icon="✦"><p className="ai-feature-copy">{analysis.coaching_advice}</p></FeatureCard>
        </>
      )}
    </div>
  )
}

function PlannerPage() {
  const [available, setAvailable] = useState(90)
  const [session, setSession] = useState(30)
  const [days, setDays] = useState<string[]>(WEEKDAYS.slice(0, 5))
  const [goal, setGoal] = useState('')
  const [plan, setPlan] = useState<StudyPlan | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  function toggleDay(day: string) {
    setDays((current) => current.includes(day) ? current.filter((item) => item !== day) : [...current, day])
  }
  async function generate(event?: FormEvent) {
    event?.preventDefault()
    setLoading(true)
    setError('')
    try {
      setPlan(await request<StudyPlan>('/api/v1/student/planner', {
        method: 'POST',
        body: JSON.stringify({
          available_minutes_per_day: available,
          session_minutes: session,
          study_days: days,
          goal: goal || null,
        }),
      }))
    } catch (requestError) {
      setError(messageFrom(requestError, 'Your study plan could not be generated.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="student-content ai-feature-page">
      <SectionHeading eyebrow="A REALISTIC ROUTE THROUGH YOUR WORK" title="AI Study Planner" detail="Plan focused sessions around your assigned tasks, deadlines, and available study time. Nothing is marked complete or changed." />
      <section className="student-card planner-controls">
        <form onSubmit={(event) => void generate(event)}>
          <div className="planner-number-fields">
            <label>Available minutes each study day<input type="number" min={15} max={480} step={15} value={available} onChange={(event) => setAvailable(Number(event.target.value))} required /></label>
            <label>Preferred session length<input type="number" min={10} max={120} step={5} value={session} onChange={(event) => setSession(Number(event.target.value))} required /></label>
          </div>
          <fieldset className="planner-days"><legend>Study days</legend>{WEEKDAYS.map((day) => <label key={day}><input type="checkbox" checked={days.includes(day)} onChange={() => toggleDay(day)} />{day.slice(0, 3)}</label>)}</fieldset>
          <label className="planner-goal">Optional study goal<input value={goal} onChange={(event) => setGoal(event.target.value)} maxLength={500} placeholder="For example, make steady progress on upcoming tasks" /></label>
          <div className="planner-submit-row"><p>Plan is advisory. Task statuses and deadlines are never changed.</p><button className="student-button student-button-primary" type="submit" disabled={loading}>{loading ? 'Building your plan…' : plan ? 'Regenerate plan' : 'Generate plan'}</button></div>
        </form>
      </section>
      {error && <Notice kind="error">{error}</Notice>}
      {loading && <div className="student-state" role="status">Building a schedule from your actual assigned work…</div>}
      {plan && (
        <div className="planner-results">
          {plan.message && <section className="student-card ai-empty-state"><span aria-hidden="true">✓</span><h2>Your task queue is clear.</h2><p>{plan.message}</p></section>}
          {!plan.message && <>
            <div className="planner-result-grid">
              <FeatureCard title="Today's Plan" icon="◷"><SessionList sessions={plan.today_sessions} empty="No sessions are scheduled for today. Your next selected study day is listed below." /></FeatureCard>
              <FeatureCard title="Upcoming Plan" icon="▦"><SessionList sessions={plan.upcoming_sessions} empty="No upcoming sessions were scheduled." /></FeatureCard>
            </div>
            <FeatureCard title="Priority Explanation" icon="↗"><p className="ai-feature-copy">{plan.priority_explanation}</p><p className="ai-feature-copy">{plan.study_advice}</p></FeatureCard>
            {!!plan.unscheduled_tasks.length && <FeatureCard title="Still to Schedule" icon="!"><TagList values={plan.unscheduled_tasks.map((task) => `${task.title} · ${task.remaining_minutes} min remaining`)} /></FeatureCard>}
            <p className="ai-last-analyzed">Plan generated {new Date(plan.generated_at).toLocaleString()}</p>
          </>}
        </div>
      )}
    </div>
  )
}

function PracticePage() {
  const [topics, setTopics] = useState<string[]>([])
  const [weakTopics, setWeakTopics] = useState<string[]>([])
  const [difficulty, setDifficulty] = useState('Beginner')
  const [topic, setTopic] = useState('')
  const [practiceType, setPracticeType] = useState(PRACTICE_TYPES[0])
  const [questionCount, setQuestionCount] = useState(5)
  const [practice, setPractice] = useState<PracticeSet | null>(null)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [result, setResult] = useState<PracticeResult | null>(null)
  const [topicsLoading, setTopicsLoading] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    request<{ topics: string[]; weak_topics: string[]; default_difficulty: string }>('/api/v1/student/practice/topics')
      .then((data) => {
        if (!active) return
        setTopics(data.topics)
        setWeakTopics(data.weak_topics)
        setTopic(data.weak_topics[0] ?? data.topics[0] ?? '')
        setDifficulty(data.default_difficulty)
      })
      .catch((requestError: unknown) => {
        if (active) setError(messageFrom(requestError, 'Your recorded practice topics could not be loaded.'))
      })
      .finally(() => { if (active) setTopicsLoading(false) })
    return () => { active = false }
  }, [])

  async function generate(event: FormEvent) {
    event.preventDefault()
    setLoading(true)
    setError('')
    setPractice(null)
    setResult(null)
    setAnswers({})
    try {
      setPractice(await request<PracticeSet>('/api/v1/student/practice/generate', {
        method: 'POST',
        body: JSON.stringify({ topic, difficulty, question_count: questionCount, practice_type: practiceType }),
      }))
    } catch (requestError) {
      setError(messageFrom(requestError, 'Practice questions could not be generated.'))
    } finally {
      setLoading(false)
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!practice) return
    setLoading(true)
    setError('')
    try {
      setResult(await request<PracticeResult>(`/api/v1/student/practice/${practice.practice_id}/submit`, {
        method: 'POST',
        body: JSON.stringify({ answers: practice.questions.map((item) => ({ question_id: item.question_id, answer: answers[item.question_id] ?? '' })) }),
      }))
    } catch (requestError) {
      setError(messageFrom(requestError, 'Your answers could not be evaluated.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="student-content ai-feature-page">
      <SectionHeading eyebrow="PRACTICE WHAT YOUR RECORDS SHOW" title="Practice & Skill Builder" detail="Generate original questions for topics in your assigned work and recorded skills. Correct answers stay hidden until you submit." />
      <section className="student-card practice-controls">
        <form onSubmit={(event) => void generate(event)}>
          <label>Topic<select value={topic} onChange={(event) => setTopic(event.target.value)} disabled={topicsLoading || !topics.length} required>{topics.map((item) => <option key={item} value={item}>{item}{weakTopics.includes(item) ? ' · developing skill' : ''}</option>)}</select></label>
          <label>Difficulty<select value={difficulty} onChange={(event) => setDifficulty(event.target.value)}>{DIFFICULTIES.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label>Practice type<select value={practiceType} onChange={(event) => setPracticeType(event.target.value)}>{PRACTICE_TYPES.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label>Questions<select value={questionCount} onChange={(event) => setQuestionCount(Number(event.target.value))}>{[3, 5, 8, 10].map((count) => <option key={count} value={count}>{count}</option>)}</select></label>
          <button className="student-button student-button-primary" type="submit" disabled={loading || topicsLoading || !topic}>{loading && !practice ? 'Creating practice…' : practice ? 'Generate new practice' : 'Generate practice'}</button>
        </form>
        {!topicsLoading && !topics.length && <p className="ai-muted">Practice becomes available when a task or skill topic is recorded for your student account.</p>}
      </section>
      {error && <Notice kind="error">{error}</Notice>}
      {loading && !practice && <div className="student-state" role="status">Creating practice from your selected recorded topic…</div>}
      {practice && !result && (
        <form className="practice-question-list" onSubmit={(event) => void submit(event)}>
          <div className="practice-set-heading"><div><p className="student-eyebrow">{practice.topic} · {practice.difficulty}</p><h2>{practice.practice_type}</h2></div><span>{practice.question_count} questions</span></div>
          {practice.questions.map((item, index) => (
            <article className="student-card practice-question" key={item.question_id}>
              <span className="practice-question-index">QUESTION {String(index + 1).padStart(2, '0')}</span>
              <h3>{item.question}</h3>
              {item.options.length ? <fieldset className="practice-options"><legend className="visually-hidden">Answer question {index + 1}</legend>{item.options.map((option) => <label key={option}><input type="radio" name={`question-${item.question_id}`} value={option} checked={answers[item.question_id] === option} onChange={() => setAnswers((current) => ({ ...current, [item.question_id]: option }))} />{option}</label>)}</fieldset>
                : <label className="practice-written-answer">Your answer<textarea rows={4} maxLength={2000} value={answers[item.question_id] ?? ''} onChange={(event) => setAnswers((current) => ({ ...current, [item.question_id]: event.target.value }))} required /></label>}
            </article>
          ))}
          <button className="student-button student-button-primary" type="submit" disabled={loading || practice.questions.some((item) => !answers[item.question_id]?.trim())}>{loading ? 'Checking your answers…' : 'Submit answers'}</button>
        </form>
      )}
      {loading && practice && !result && <div className="student-state" role="status">Evaluating your answers…</div>}
      {result && <PracticeReview result={result} onRestart={() => { setResult(null); setPractice(null); setAnswers({}) }} />}
    </div>
  )
}

function PracticeReview({ result, onRestart }: { result: PracticeResult; onRestart: () => void }) {
  return (
    <section className="student-card practice-review" aria-live="polite">
      <div className="practice-score"><span>YOUR SCORE</span><strong>{result.score}%</strong><small>{result.correct_count} of {result.question_count} correct</small></div>
      <h2>Review & learn</h2>
      <div className="practice-result-list">{result.results.map((item) => (
        <article className={`practice-result ${item.is_correct ? 'correct' : 'incorrect'}`} key={item.question_id}>
          <div><span>{item.is_correct ? 'Correct' : 'Review this answer'} · {item.score}%</span><h3>{item.question}</h3></div>
          <p><strong>Your answer:</strong> {item.student_answer}</p>
          <p><strong>Answer:</strong> {item.correct_answer}</p>
          <p>{item.explanation}</p>
          <p className="practice-feedback">{item.feedback}</p>
        </article>
      ))}</div>
      {!!result.weak_areas.length && <div className="practice-weak"><strong>Topics to revisit</strong><TagList values={result.weak_areas} /></div>}
      <FeatureCard title="AI recommendation" icon="✦"><p className="ai-feature-copy">{result.recommendation}</p></FeatureCard>
      <button className="student-button student-button-primary" type="button" onClick={onRestart}>Build another practice set</button>
    </section>
  )
}

function ReportPage() {
  const [reports, setReports] = useState<ProgressReport[]>([])
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    request<ProgressReport[]>('/api/v1/student/report/history')
      .then((data) => { if (active) setReports(data) })
      .catch((requestError: unknown) => {
        if (active) setError(messageFrom(requestError, 'Saved reports could not be loaded.'))
      })
      .finally(() => { if (active) setLoadingHistory(false) })
    return () => { active = false }
  }, [])

  async function generate() {
    setGenerating(true)
    setError('')
    try {
      const report = await request<ProgressReport>('/api/v1/student/report', { method: 'POST' })
      setReports((current) => [report, ...current.filter((item) => item.id !== report.id)])
    } catch (requestError) {
      setError(messageFrom(requestError, 'Your progress report could not be generated.'))
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="student-content ai-feature-page">
      <div className="student-page-heading">
        <SectionHeading eyebrow="PROGRESS GROUNDED IN YOUR RECORDS" title="Progress & Career Report" detail="Review deterministic assignment metrics alongside AI learning and career-direction suggestions based on your actual progress." />
        <button className="student-button student-button-primary" type="button" onClick={() => void generate()} disabled={generating}>{generating ? 'Preparing your report…' : 'Generate AI Report'}</button>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {loadingHistory && <div className="student-state" role="status">Loading your saved reports…</div>}
      {!loadingHistory && !reports.length && !generating && <section className="student-card ai-empty-state"><span aria-hidden="true">▤</span><h2>Your learning report starts with your records.</h2><p>Generate a report to see actual task counts, recorded scores, strengths, learning gaps, and grounded next steps.</p></section>}
      {generating && <div className="student-state" role="status">Reviewing your recorded progress and preparing recommendations…</div>}
      {reports.map((report) => <ProgressReportCard report={report} key={report.id} />)}
    </div>
  )
}

function ProgressReportCard({ report }: { report: ProgressReport }) {
  const { content } = report
  const metrics = [
    ['Total tasks', content.metrics.total_tasks],
    ['Completed', content.metrics.completed_tasks],
    ['In progress', content.metrics.in_progress_tasks],
    ['Pending', content.metrics.pending_tasks],
    ['Overdue', content.metrics.overdue_tasks],
    ['Completion', `${content.metrics.completion_percentage}%`],
    ['Performance', content.metrics.average_recorded_performance === null ? 'Not recorded' : `${content.metrics.average_recorded_performance}%`],
  ]
  return (
    <article className="student-card progress-report-card">
      <header><div><p className="student-eyebrow">PERSONAL LEARNING REPORT · {content.report_date}</p><h2>{content.title}</h2></div><span>{new Date(report.created_at.replace(' ', 'T') + 'Z').toLocaleDateString()}</span></header>
      <div className="report-metrics">{metrics.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
      <p className="report-performance-category">Performance category: <strong>{content.metrics.performance_category}</strong></p>
      <FeatureCard title="Summary" icon="◈"><p className="ai-feature-copy">{content.summary}</p></FeatureCard>
      <div className="report-analysis-grid">
        <FeatureCard title="Key strengths" icon="↗"><TagList values={content.strengths} empty="No specific strengths were available." tone="positive" /></FeatureCard>
        <FeatureCard title="Weak skills" icon="◎"><TagList values={content.weak_skills} empty="No specific weak skills were identified." tone="caution" /></FeatureCard>
        <FeatureCard title="Learning gaps" icon="⌁"><TagList values={content.learning_gaps} empty="No learning gaps were identified." /></FeatureCard>
        <FeatureCard title="Recommended topics" icon="▦"><TagList values={content.recommended_topics} empty="No topic recommendation is available." /></FeatureCard>
        <FeatureCard title="Next skills" icon="➜"><TagList values={content.next_skills} empty="No next skill was recommended." /></FeatureCard>
        <FeatureCard title="Career-oriented directions" icon="✦"><TagList values={content.career_suggestions} empty="No career direction was suggested." /></FeatureCard>
      </div>
      <FeatureCard title="Overall recommendation" icon="✧"><p className="ai-feature-copy">{content.overall_recommendation}</p></FeatureCard>
    </article>
  )
}

function SessionList({ sessions, empty }: { sessions: PlannedSession[]; empty: string }) {
  if (!sessions.length) return <p className="ai-muted">{empty}</p>
  return <ol className="planner-session-list">{sessions.map((item) => (
    <li key={`${item.assignment_id}-${item.study_date}-${item.session_number}`}>
      <div className="planner-session-date"><strong>{new Date(`${item.study_date}T00:00:00`).toLocaleDateString(undefined, { weekday: 'short' })}</strong><span>{new Date(`${item.study_date}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</span></div>
      <div className="planner-session-copy"><strong>{item.title}</strong><span>{item.topic} · {item.minutes} min · {item.status}</span><p>{item.reason}</p></div>
      {item.is_overdue && <span className="task-status status-overdue">Overdue</span>}
    </li>
  ))}</ol>
}

function TagList({ values, empty, tone }: { values: string[]; empty?: string; tone?: 'positive' | 'caution' }) {
  if (!values.length) return <p className="ai-muted">{empty ?? 'No recorded items to display.'}</p>
  return <ul className={`ai-tag-list${tone ? ` ${tone}` : ''}`}>{values.map((value, index) => <li key={`${value}-${index}`}>{value}</li>)}</ul>
}

function formatDate(value: string) {
  const parsed = new Date(`${value}T00:00:00`)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export default function StudentAISection({ path }: PageProps) {
  if (path.endsWith('/assistant')) return <AssistantPage />
  if (path.endsWith('/coach')) return <CoachPage />
  if (path.endsWith('/planner')) return <PlannerPage />
  if (path.endsWith('/practice')) return <PracticePage />
  return <ReportPage />
}
