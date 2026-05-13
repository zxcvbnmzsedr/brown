import type {
  Asset,
  AssetPayload,
  AssetSearchResult,
  AssetPriceStatus,
  BucketPayload,
  CsvImportResult,
  FetchResult,
  GroupPayload,
  OpeningPosition,
  OpeningPositionPayload,
  OpeningPositionUpdate,
  PortfolioBucket,
  PricePayload,
  RebalanceConfig,
  RebalanceHistoryCreate,
  RebalanceHistoryRead,
  RebalancePlanResponse,
  RebalanceResponse,
  Snapshot,
  SnapshotHistoryRead,
  Transaction,
  TransactionPayload,
  TransactionUpdate,
  CurrentUser,
  LoginResponse,
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

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  })

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

  if (response.headers.get('content-type')?.includes('text/csv')) {
    return response.blob() as Promise<T>
  }

  return response.json() as Promise<T>
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
  getMe: () => request<CurrentUser>('/auth/me'),

  // Structure
  getStructure: () => request<PortfolioBucket[]>('/portfolio/structure'),

  // Buckets
  createBucket: (payload: BucketPayload) =>
    request<PortfolioBucket>('/buckets', { method: 'POST', body: JSON.stringify(payload) }),
  updateBucket: (id: number, payload: BucketPayload) =>
    request<PortfolioBucket>(`/buckets/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteBucket: (id: number) => request<void>(`/buckets/${id}`, { method: 'DELETE' }),

  // Groups
  createGroup: (payload: GroupPayload) =>
    request<void>('/groups', { method: 'POST', body: JSON.stringify(payload) }),
  updateGroup: (id: number, payload: GroupPayload) =>
    request<void>(`/groups/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteGroup: (id: number) => request<void>(`/groups/${id}`, { method: 'DELETE' }),

  // Assets
  listAssets: () => request<Asset[]>('/assets'),
  searchAssets: (query: string) => request<AssetSearchResult[]>(`/assets/search?q=${encodeURIComponent(query)}`),
  createAsset: (payload: AssetPayload) =>
    request<Asset>('/assets', { method: 'POST', body: JSON.stringify(payload) }),
  updateAsset: (id: number, payload: AssetPayload) =>
    request<Asset>(`/assets/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteAsset: (id: number) => request<void>(`/assets/${id}`, { method: 'DELETE' }),

  // Prices
  updatePrice: (assetId: number, payload: PricePayload) =>
    request<void>(`/prices/${assetId}`, { method: 'PUT', body: JSON.stringify(payload) }),
  fetchAllPrices: () => request<FetchResult>('/prices/fetch', { method: 'POST' }),
  fetchAssetPrice: (assetId: number) =>
    request<FetchResult>(`/prices/fetch/${assetId}`, { method: 'POST' }),
  getPriceStatus: () => request<AssetPriceStatus[]>('/prices/status'),

  // Transactions
  listTransactions: () => request<Transaction[]>('/transactions'),
  createTransaction: (payload: TransactionPayload) =>
    request<Transaction>('/transactions', { method: 'POST', body: JSON.stringify(payload) }),
  updateTransaction: (id: number, payload: TransactionUpdate) =>
    request<Transaction>(`/transactions/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteTransaction: (id: number) => request<void>(`/transactions/${id}`, { method: 'DELETE' }),

  // Opening Positions
  listOpeningPositions: () => request<OpeningPosition[]>('/opening-positions'),
  createOpeningPosition: (payload: OpeningPositionPayload) =>
    request<OpeningPosition>('/opening-positions', { method: 'POST', body: JSON.stringify(payload) }),
  updateOpeningPosition: (id: number, payload: OpeningPositionUpdate) =>
    request<OpeningPosition>(`/opening-positions/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteOpeningPosition: (id: number) => request<void>(`/opening-positions/${id}`, { method: 'DELETE' }),

  // Portfolio
  getSnapshot: () => request<Snapshot>('/portfolio/snapshot'),

  // Rebalance
  getRebalance: () => request<RebalanceResponse>('/rebalance/suggestion'),
  getRebalanceConfig: () => request<RebalanceConfig>('/rebalance/config'),
  updateRebalanceConfig: (config: RebalanceConfig) =>
    request<RebalanceConfig>('/rebalance/config', { method: 'PUT', body: JSON.stringify(config) }),
  getRebalancePlan: () => request<RebalancePlanResponse>('/rebalance/plan'),

  // History
  recordSnapshot: () => request<SnapshotHistoryRead>('/history/snapshot', { method: 'POST' }),
  listSnapshots: (limit = 365) => request<SnapshotHistoryRead[]>(`/history/snapshot?limit=${limit}`),
  recordRebalance: (payload: RebalanceHistoryCreate) =>
    request<RebalanceHistoryRead>('/history/rebalance', { method: 'POST', body: JSON.stringify(payload) }),
  recordRebalanceFromPlan: () =>
    request<RebalanceHistoryRead>('/history/rebalance/from-plan', { method: 'POST' }),
  listRebalances: (limit = 100) => request<RebalanceHistoryRead[]>(`/history/rebalance?limit=${limit}`),

  // CSV Export/Import
  exportTransactions: () => request<Blob>('/export/transactions'),
  importTransactions: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<CsvImportResult>('/import/transactions', { method: 'POST', body: form })
  },
}
