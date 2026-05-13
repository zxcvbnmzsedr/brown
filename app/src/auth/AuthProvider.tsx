import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, clearAccessToken, getAccessToken } from '../api/client'
import type { CurrentUser } from '../types'
import { AuthContext } from './auth-context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [loading, setLoading] = useState(() => Boolean(getAccessToken()))

  useEffect(() => {
    if (!getAccessToken()) {
      return
    }

    let active = true
    api.getMe()
      .then((currentUser) => {
        if (active) setUser(currentUser)
      })
      .catch(() => {
        clearAccessToken()
        if (active) setUser(null)
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const result = await api.login(email, password)
    setUser(result.user)
  }, [])

  const register = useCallback(async (email: string, password: string, name: string | null) => {
    const result = await api.register(email, password, name)
    setUser(result.user)
  }, [])

  const logout = useCallback(() => {
    clearAccessToken()
    setUser(null)
  }, [])

  const value = useMemo(() => ({ user, loading, login, register, logout }), [loading, login, logout, register, user])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
