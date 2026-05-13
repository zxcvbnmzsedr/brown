export type AssetType = 'stock' | 'fund' | 'money_market' | 'cash' | 'crypto'
export type TransactionType = 'buy' | 'sell'
export type PriceState = 'fresh' | 'stale' | 'missing' | 'cash'
export type MonitorState = 'ok' | 'watch' | 'warning' | 'rebalance' | 'incomplete'

export interface CurrentUser {
  id: number
  email: string
  name: string | null
}

export interface LoginResponse {
  access_token: string
  token_type: 'bearer'
  user: CurrentUser
}

export interface AssetGroup {
  id: number
  bucket_id: number
  bucket_name: string | null
  name: string
  target_weight: number
  display_order: number
}

export interface PortfolioBucket {
  id: number
  name: string
  target_weight: number
  display_order: number
  groups: AssetGroup[]
}

export interface BucketPayload {
  name: string
  target_weight: number
  display_order: number
}

export interface GroupPayload {
  bucket_id: number
  name: string
  target_weight: number
  display_order: number
}

export interface Asset {
  id: number
  group_id: number | null
  group_name: string | null
  bucket_id: number | null
  bucket_name: string | null
  name: string
  platform: string | null
  type: AssetType
  code: string | null
  exchange: string | null
  target_weight: number
  is_active: boolean
  include_in_portfolio: boolean
  created_at: string
  latest_price: number | null
  transaction_count: number
  price_count: number
}

export interface AssetSearchResult {
  id: string
  source: 'local' | 'akshare'
  existing_asset_id: number | null
  name: string
  type: AssetType
  code: string | null
  exchange: string | null
  platform: string | null
  latest_price: number | null
  include_in_portfolio: boolean
  group_name: string | null
  bucket_name: string | null
}

export interface AssetPayload {
  group_id: number | null
  name: string
  platform: string | null
  type: AssetType
  code: string | null
  exchange: string | null
  target_weight: number
  is_active: boolean
  include_in_portfolio: boolean
}

export interface PricePayload {
  price: number
  date?: string
}

export interface Transaction {
  id: number
  date: string
  asset_id: number
  asset_name: string
  type: TransactionType
  qty: number
  price: number
  fee: number
  note: string | null
  created_at: string
}

export interface TransactionPayload {
  date: string
  asset_id?: number | null
  asset?: {
    name: string
    type: AssetType
    code: string | null
    exchange: string | null
    platform: string | null
    latest_price: number | null
  } | null
  type: TransactionType
  qty: number
  price: number
  fee: number
  note: string | null
}

export interface OpeningPosition {
  id: number
  asset_id: number
  asset_name: string
  asset_code: string | null
  asset_exchange: string | null
  include_in_portfolio: boolean
  date: string
  qty: number
  cost_price: number
  current_price: number
  note: string | null
  created_at: string
}

export interface OpeningPositionPayload {
  asset_id: number
  date: string
  qty: number
  cost_price: number
  current_price: number
  note: string | null
}

export interface OpeningPositionUpdate {
  asset_id?: number
  date?: string
  qty?: number
  cost_price?: number
  current_price?: number
  note?: string | null
}

export interface SnapshotItem {
  asset_id: number
  bucket_id: number | null
  bucket_name: string | null
  group_id: number | null
  group_name: string | null
  include_in_portfolio: boolean
  name: string
  platform: string | null
  type: AssetType
  code: string | null
  exchange: string | null
  target_weight: number
  quantity: number
  cost_basis: number
  average_cost: number | null
  current_price: number | null
  price_date: string | null
  price_fetched_at: string | null
  price_age_days: number | null
  price_state: PriceState
  current_value: number
  actual_weight: number
  drift: number
}

export interface SnapshotGroup {
  group_id: number
  bucket_id: number
  name: string
  target_weight: number
  current_value: number
  actual_weight: number
  drift: number
}

export interface SnapshotBucket {
  bucket_id: number
  name: string
  target_weight: number
  current_value: number
  actual_weight: number
  drift: number
  lower_bound: number | null
  upper_bound: number | null
  distance_to_lower: number | null
  distance_to_upper: number | null
  monitor_state: MonitorState
  groups: SnapshotGroup[]
}

export interface Snapshot {
  as_of: string
  total_value: number
  total_holdings_value: number
  target_weight_total: number
  price_state: MonitorState
  stale_price_count: number
  missing_price_count: number
  pending_classification_count: number
  pending_classification_value: number
  buckets: SnapshotBucket[]
  items: SnapshotItem[]
  all_items: SnapshotItem[]
}

export interface RebalanceSuggestion {
  scope: 'bucket'
  bucket_id: number
  name: string
  action: 'buy' | 'sell'
  drift: number
  target_value: number
  current_value: number
  amount: number
  candidate_assets: string[]
}

export interface RebalanceResponse {
  threshold: number
  triggered: boolean
  total_value: number
  suggestions: RebalanceSuggestion[]
}

// --- Phase 3: Enhanced Rebalance Types ---

export interface RebalanceConfig {
  mode: 'classic_35_15' | 'custom'
  upper_threshold: number
  lower_threshold: number
  watch_drift: number
  warning_drift: number
  max_price_age_days: number
}

export interface AssetAction {
  asset_id: number
  asset_name: string
  asset_code: string | null
  current_qty: number
  current_price: number | null
  current_value: number
  action: 'buy' | 'sell' | 'hold'
  target_value_delta: number
  suggested_qty_delta: number
  suggested_shares: number | null
  estimated_trade_amount: number
}

export interface GroupRebalanceDetail {
  group_id: number
  group_name: string
  current_value: number
  target_value: number
  value_delta: number
  assets: AssetAction[]
}

export interface BucketRebalanceDetail {
  bucket_id: number
  bucket_name: string
  target_weight: number
  current_value: number
  current_weight: number
  target_value: number
  value_delta: number
  action: 'buy' | 'sell' | 'hold'
  lower_bound: number
  upper_bound: number
  distance_to_lower: number
  distance_to_upper: number
  monitor_state: MonitorState
  groups: GroupRebalanceDetail[]
}

export interface RebalancePlanResponse {
  config: RebalanceConfig
  status: MonitorState
  status_label: string
  status_message: string
  triggered: boolean
  total_value: number
  as_of: string
  trigger_reasons: string[]
  price_warnings: string[]
  buckets: BucketRebalanceDetail[]
  trade_list: AssetAction[]
}

export interface FetchResult {
  updated: number
  errors: string[]
}

export interface AssetPriceStatus {
  asset_id: number
  asset_name: string
  last_fetched_at: string | null
  latest_price: number | null
  price_age_days: number | null
  price_state: PriceState
}

export interface TransactionUpdate {
  date?: string
  type?: TransactionType
  asset_id?: number
  qty?: number
  price?: number
  fee?: number
  note?: string | null
}

export interface SnapshotHistoryRead {
  id: number
  recorded_at: string
  total_value: number
  bucket_data: string
  item_data: string
}

export interface RebalanceHistoryRead {
  id: number
  executed_at: string
  config_mode: string
  total_value: number
  trigger_reasons: string
  trade_data: string
  note: string | null
}

export interface RebalanceHistoryCreate {
  config_mode: string
  total_value: number
  trigger_reasons: string
  trade_data: string
  note: string | null
}

export interface ElectronAPI {
  getAppVersion: () => Promise<string>
  getPlatform: () => string
  minimizeWindow: () => void
  maximizeWindow: () => void
  closeWindow: () => void
  notifyRebalance: (title: string, body: string) => Promise<boolean>
  isElectron: boolean
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI
  }
}

export interface CsvImportResult {
  imported: number
  errors: string[]
}
