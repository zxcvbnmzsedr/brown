import { Eye, EyeOff, Loader2, LogIn, Mail, ShieldCheck, UserPlus } from 'lucide-react'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export function LoginPage() {
  const { user, login, register } = useAuth()
  const location = useLocation()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [passwordVisible, setPasswordVisible] = useState(false)

  if (user) {
    const to = typeof location.state === 'object' && location.state && 'from' in location.state
      ? String(location.state.from)
      : '/'
    return <Navigate to={to} replace />
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      if (mode === 'login') {
        await login(email, password)
      } else {
        await register(email, password, name.trim() || null)
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '操作失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <form className="login-panel" onSubmit={submit}>
        <header className="login-brand">
          <span className="brand-mark">B</span>
          <div className="login-brand-text">
            <strong>Brown</strong>
            <small>资产统计 · 永久组合</small>
          </div>
        </header>

        <div className="login-heading">
          <h1>{mode === 'login' ? '登录资产工作台' : '创建资产账户'}</h1>
          <p>维护组合、现金账户、交易流水和再平衡统计</p>
        </div>

        <div className="mode-switch" role="tablist" aria-label="认证方式">
          <button type="button" className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>
            登录
          </button>
          <button type="button" className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>
            注册
          </button>
        </div>

        {error ? (
          <div className="alert login-alert" role="alert">
            {error}
          </div>
        ) : null}

        <div className="login-fields">
          {mode === 'register' ? (
            <label className="login-field">
              <span className="login-field-label">姓名</span>
              <div className="login-input-wrap">
                <UserPlus size={16} className="login-input-icon" aria-hidden="true" />
                <input value={name} onChange={(event) => setName(event.target.value)} placeholder="可选" />
              </div>
            </label>
          ) : null}

          <label className="login-field">
            <span className="login-field-label">邮箱</span>
            <div className="login-input-wrap">
              <Mail size={16} className="login-input-icon" aria-hidden="true" />
              <input
                required
                autoComplete="email"
                inputMode="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </div>
          </label>

          <label className="login-field">
            <span className="login-field-label">密码</span>
            <div className="login-input-wrap">
              <ShieldCheck size={16} className="login-input-icon" aria-hidden="true" />
              <input
                required
                minLength={mode === 'register' ? 6 : 1}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                type={passwordVisible ? 'text' : 'password'}
                placeholder="请输入密码"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              <button
                type="button"
                className="login-input-toggle"
                onClick={() => setPasswordVisible((visible) => !visible)}
                aria-label={passwordVisible ? '隐藏密码' : '显示密码'}
                tabIndex={-1}
              >
                {passwordVisible ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </label>
        </div>

        <button className="primary-button login-submit" type="submit" disabled={submitting}>
          {submitting ? (
            <>
              <Loader2 size={16} className="login-spin" />
              <span>处理中...</span>
            </>
          ) : (
            <>
              <LogIn size={16} />
              <span>{mode === 'login' ? '登录' : '注册并进入'}</span>
            </>
          )}
        </button>
      </form>
    </main>
  )
}
