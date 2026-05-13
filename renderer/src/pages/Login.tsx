import { Eye, EyeOff, Loader2, LogIn, Mail, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export function LoginPage() {
  const { user, login } = useAuth()
  const location = useLocation()
  const [email, setEmail] = useState('')
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
      await login(email, password)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '登录失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <div className="login-aurora" aria-hidden="true">
        <span className="login-aurora-blob login-aurora-blob-a" />
        <span className="login-aurora-blob login-aurora-blob-b" />
        <span className="login-aurora-blob login-aurora-blob-c" />
      </div>

      <form className="login-panel" onSubmit={submit}>
        <header className="login-brand">
          <span className="brand-mark">B</span>
          <div className="login-brand-text">
            <strong>Brown</strong>
            <small>永久组合 · 资产配置工作台</small>
          </div>
        </header>

        <div className="login-heading">
          <h1>欢迎回来</h1>
          <p>登录以同步您的投资组合与再平衡计划</p>
        </div>

        {error ? (
          <div className="alert login-alert" role="alert">
            {error}
          </div>
        ) : null}

        <div className="login-fields">
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
                autoComplete="current-password"
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
              <span>登录中…</span>
            </>
          ) : (
            <>
              <LogIn size={16} />
              <span>登录</span>
            </>
          )}
        </button>

        <footer className="login-footer">
          <span>© {new Date().getFullYear()} Brown Portfolio</span>
          <span className="login-footer-divider">·</span>
          <span>本地优先 · 数据加密保存</span>
        </footer>
      </form>
    </main>
  )
}
