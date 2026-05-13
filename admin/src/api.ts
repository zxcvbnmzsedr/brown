import type {
  AdminLoginResponse,
  AdminUser,
  Instrument,
  InstrumentPayload,
  InstrumentSyncResult,
  PriceFetchResult,
  PriceStatus,
  TradingPlatform,
  TradingPlatformPayload,
} from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8765'
const TOKEN_KEY = 'brown.admin.access_token'

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
  const headers = new Headers(options.headers)
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  const token = getAccessToken()
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
    const result = await request<AdminLoginResponse>('/admin/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    setAccessToken(result.access_token)
    return result
  },
  getMe: () => request<AdminUser>('/admin/auth/me'),

  listInstruments: (params: { q?: string; instrument_type?: string; market?: string; include_inactive?: boolean } = {}) =>
    request<Instrument[]>(`/admin/instruments${toQuery(params)}`),
  createInstrument: (payload: InstrumentPayload) =>
    request<Instrument>('/admin/instruments', { method: 'POST', body: JSON.stringify(payload) }),
  updateInstrument: (id: number, payload: InstrumentPayload) =>
    request<Instrument>(`/admin/instruments/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  toggleInstrument: (id: number) => request<Instrument>(`/admin/instruments/${id}/toggle`, { method: 'POST' }),
  syncInstruments: (query: string, limit = 20) =>
    request<InstrumentSyncResult>('/admin/instruments/sync', { method: 'POST', body: JSON.stringify({ query, limit }) }),

  listTradingPlatforms: () => request<TradingPlatform[]>('/admin/trading-platforms'),
  createTradingPlatform: (payload: TradingPlatformPayload) =>
    request<TradingPlatform>('/admin/trading-platforms', { method: 'POST', body: JSON.stringify(payload) }),
  updateTradingPlatform: (id: number, payload: TradingPlatformPayload) =>
    request<TradingPlatform>(`/admin/trading-platforms/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  toggleTradingPlatform: (id: number) =>
    request<TradingPlatform>(`/admin/trading-platforms/${id}/toggle`, { method: 'POST' }),

  listPriceStatus: (params: { q?: string; price_state?: string } = {}) =>
    request<PriceStatus[]>(`/admin/instrument-prices/status${toQuery(params)}`),
  updatePrice: (instrumentId: number, price: number, date?: string) =>
    request('/admin/instrument-prices/manual', { method: 'PUT', body: JSON.stringify({ instrument_id: instrumentId, price, date }) }),
  fetchPrices: () => request<PriceFetchResult>('/admin/instrument-prices/fetch', { method: 'POST' }),
}
