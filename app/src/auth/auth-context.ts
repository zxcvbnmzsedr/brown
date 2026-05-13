import { createContext } from 'react'
import type { CurrentUser } from '../types'

export interface AuthContextValue {
  user: CurrentUser | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name: string | null) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)
