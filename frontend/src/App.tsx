import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import AdminPanel from './AdminPanel'
import StudentPanel from './StudentPanel'
import './App.css'
import { request } from './services/api'

function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" to="/" aria-label="Skillonex Academy home">
          <span className="brand-mark">S</span>
          <span>Skillonex <small>ACADEMY</small></span>
        </Link>
        <nav aria-label="Main navigation">
          <Link to="/student/login">Student</Link>
          <Link to="/admin/login">Admin</Link>
        </nav>
      </header>
      <main>{children}</main>
      <footer>Skillonex Academy <span>·</span> Learn with purpose.</footer>
    </div>
  )
}

function Landing() {
  return (
    <Shell>
      <section className="hero">
        <p className="eyebrow"><span className="spark" /> ACADEMIC PROGRESS, MADE PERSONAL</p>
        <h1>Make every learning step <em>count.</em></h1>
        <p className="hero-copy">
          A focused space for students to move forward and educators to see the bigger picture.
        </p>
        <div className="role-cards">
          <Link className="role-card student-card" to="/student/login">
            <span className="card-index">01 / STUDENT</span>
            <span className="role-title">Your learning, in motion.</span>
            <span className="role-desc">See your tasks and personal progress in one place.</span>
            <span className="card-action">Student sign in <b aria-hidden="true">↗</b></span>
          </Link>
          <Link className="role-card admin-card" to="/admin/login">
            <span className="card-index">02 / ADMINISTRATION</span>
            <span className="role-title">Guide the next breakthrough.</span>
            <span className="role-desc">A clear foundation for managing learning programs.</span>
            <span className="card-action">Admin sign in <b aria-hidden="true">↗</b></span>
          </Link>
        </div>
      </section>
    </Shell>
  )
}

function AuthPage({ role, signup = false }: { role: 'admin' | 'student'; signup?: boolean }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()
  const isAdmin = role === 'admin'

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setBusy(true)
    const values = Object.fromEntries(new FormData(event.currentTarget).entries())
    try {
      const endpoint = signup ? '/api/v1/auth/admin/signup' : `/api/v1/auth/${role}/login`
      await request(endpoint, { method: 'POST', body: JSON.stringify(values) })
      navigate(role === 'student' ? '/student/dashboard' : '/admin')
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : 'Unable to sign in.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Shell>
      <section className="auth-wrap">
        <Link to="/" className="back-link">← Back to home</Link>
        <div className="auth-card">
          <p className="eyebrow">{isAdmin ? 'ACADEMY OPERATIONS' : 'YOUR LEARNING SPACE'}</p>
          <h1>{signup ? 'Create admin account' : `${isAdmin ? 'Admin' : 'Student'} sign in`}</h1>
          <p className="muted">
            {signup ? 'Set up the first administrator account.' : 'Use your Skillonex credentials to continue.'}
          </p>
          <form onSubmit={submit}>
            {signup && (
              <label>
                Full name
                <input name="full_name" autoComplete="name" minLength={2} required />
              </label>
            )}
            <label>
              {isAdmin ? 'Email address' : 'Student ID'}
              <input
                name={isAdmin ? 'email' : 'student_id'}
                type={isAdmin ? 'email' : 'text'}
                autoComplete={isAdmin ? 'username' : 'username'}
                required
              />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                autoComplete={signup ? 'new-password' : 'current-password'}
                minLength={signup ? 12 : undefined}
                required
              />
              {signup && <small>Use at least 12 characters.</small>}
            </label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="button primary-button" type="submit" disabled={busy}>
              {busy ? 'Please wait…' : signup ? 'Create account' : 'Sign in'}
            </button>
          </form>
          {isAdmin && !signup && <p className="auth-alternate">First admin? <Link to="/admin/signup">Create the initial account</Link></p>}
          {signup && <p className="auth-alternate">Already have an account? <Link to="/admin/login">Sign in</Link></p>}
        </div>
      </section>
    </Shell>
  )
}

function App() {
  const location = useLocation()
  return (
    <Routes location={location}>
      <Route path="/" element={<Landing />} />
      <Route path="/admin/login" element={<AuthPage role="admin" />} />
      <Route path="/admin/signup" element={<AuthPage role="admin" signup />} />
      <Route path="/student/login" element={<AuthPage role="student" />} />
      <Route path="/admin/*" element={<AdminPanel />} />
      <Route path="/student/*" element={<StudentPanel />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
