import type {
  CashAccount,
  CashAccountPayload,
  CurrentUser,
  Instrument,
  InvestmentAccount,
  InvestmentAccountPayload,
  LoginResponse,
  Portfolio,
  PortfolioSnapshot,
  PortfolioTrend,
  ProfitCalendar,
  TradingPlatform,
  Transaction,
  TransactionPayload,
  UserAsset,
  UserAssetPayload,
} from '../types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8765'
const TOKEN_KEY = 'brown.access_token'

export function getAccessToken() {
  return window.localStorage.getItem(TOKEN_KEY)
}

export function setAccessToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token)
}

export function clearAccessToken() {
  window.localStorage.removeItem(TOKEN_KEY)
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getAccessToken()
  const headers = new Headers(options.headers)
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })
  if (!response.ok) {
    let message = response.statusText
    try {
      const body = await response.json()
      message = body.detail ?? message
    } catch {
      message = await response.text()
    }
    throw new Error(message)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return response.json() as Promise<T>
}

function toQuery(params: Record<string, string | number | boolean | undefined | null>) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query.set(key, String(value))
    }
  })
  const text = query.toString()
  return text ? `?${text}` : ''
}

export const api = {
  login: async (email: string, password: string) => {
    const result = await request<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    setAccessToken(result.access_token)
    return result
  },
  register: async (email: string, password: string, name: string | null) => {
    const result = await request<LoginResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, name }),
    })
    setAccessToken(result.access_token)
    return result
  },
  getMe: () => request<CurrentUser>('/auth/me'),

  listPortfolios: () => request<Portfolio[]>('/portfolios'),
  getSnapshot: (portfolioId: number) => request<PortfolioSnapshot>(`/portfolios/${portfolioId}/snapshot`),
  getTrend: (portfolioId: number, days = 90) => request<PortfolioTrend>(`/portfolios/${portfolioId}/trend${toQuery({ days })}`),
  getProfitCalendar: (portfolioId: number, year: number, month: number) =>
    request<ProfitCalendar>(`/portfolios/${portfolioId}/profit-calendar${toQuery({ year, month })}`),

  listInstruments: (q?: string, limit = 20) => request<Instrument[]>(`/instruments${toQuery({ q, limit })}`),
  listTradingPlatforms: (usage?: 'investment' | 'cash') =>
    request<TradingPlatform[]>(`/trading-platforms${toQuery({ usage })}`),

  listInvestmentAccounts: (portfolioId: number) =>
    request<InvestmentAccount[]>(`/investment-accounts${toQuery({ portfolio_id: portfolioId })}`),
  createInvestmentAccount: (payload: InvestmentAccountPayload) =>
    request<InvestmentAccount>('/investment-accounts', { method: 'POST', body: JSON.stringify(payload) }),

  listCashAccounts: (portfolioId: number) =>
    request<CashAccount[]>(`/cash-accounts${toQuery({ portfolio_id: portfolioId })}`),
  createCashAccount: (payload: CashAccountPayload) =>
    request<CashAccount>('/cash-accounts', { method: 'POST', body: JSON.stringify(payload) }),
  updateCashAccount: (id: number, payload: CashAccountPayload) =>
    request<CashAccount>(`/cash-accounts/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),

  listUserAssets: (portfolioId: number) =>
    request<UserAsset[]>(`/user-assets${toQuery({ portfolio_id: portfolioId })}`),
  createUserAsset: (payload: UserAssetPayload) =>
    request<UserAsset>('/user-assets', { method: 'POST', body: JSON.stringify(payload) }),
  updateUserAsset: (id: number, payload: UserAssetPayload) =>
    request<UserAsset>(`/user-assets/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),

  listTransactions: (portfolioId: number) =>
    request<Transaction[]>(`/transactions${toQuery({ portfolio_id: portfolioId })}`),
  createTransaction: (payload: TransactionPayload) =>
    request<Transaction>('/transactions', { method: 'POST', body: JSON.stringify(payload) }),
  updateTransaction: (id: number, payload: TransactionPayload) =>
    request<Transaction>(`/transactions/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteTransaction: (id: number) => request<void>(`/transactions/${id}`, { method: 'DELETE' }),
}
