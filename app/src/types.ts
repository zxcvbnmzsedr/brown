export type InstrumentType = 'stock' | 'fund' | 'etf' | 'bond' | 'gold' | 'crypto'
export type TransactionType = 'buy' | 'sell'

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

export interface PortfolioGroup {
  id: number
  bucket_id: number
  name: string
  target_weight: number
  display_order: number
}

export interface PortfolioBucket {
  id: number
  name: string
  target_weight: number
  display_order: number
  groups: PortfolioGroup[]
}

export interface Portfolio {
  id: number
  name: string
  base_currency: string
  strategy_type: string
  is_default: boolean
  buckets: PortfolioBucket[]
}

export interface Instrument {
  id: number
  name: string
  type: InstrumentType
  code: string | null
  exchange: string | null
  currency: string
  source: string | null
  is_active: boolean
  latest_price: number | null
  price_date: string | null
}

export interface TradingPlatform {
  id: number
  name: string
  type: string
  account_type: string | null
  display_order: number
  is_active: boolean
}

export interface InvestmentAccount {
  id: number
  portfolio_id: number
  trading_platform_id: number
  name: string
  is_active: boolean
  platform_name: string | null
  platform_type: string | null
}

export interface InvestmentAccountPayload {
  portfolio_id: number
  trading_platform_id: number
  name: string
  is_active: boolean
}

export interface CashAccount {
  id: number
  portfolio_id: number
  trading_platform_id: number | null
  name: string
  currency: string
  balance: number
  balance_date: string
  include_in_rebalance: boolean
  is_active: boolean
  platform_name: string | null
}

export interface CashAccountPayload {
  portfolio_id: number
  trading_platform_id: number | null
  name: string
  currency: string
  balance: number
  balance_date?: string | null
  include_in_rebalance: boolean
  is_active: boolean
}

export interface UserAsset {
  id: number
  portfolio_id: number
  instrument_id: number
  portfolio_group_id: number | null
  account_id: number | null
  display_name: string | null
  target_weight: number
  include_in_rebalance: boolean
  is_active: boolean
  instrument_name: string
  instrument_type: string
  instrument_code: string | null
  instrument_exchange: string | null
  group_name: string | null
  bucket_name: string | null
  account_name: string | null
  quantity: number
  cost_basis: number
  market_value: number
  latest_price: number | null
}

export interface UserAssetPayload {
  portfolio_id: number
  instrument_id: number
  portfolio_group_id: number | null
  account_id: number | null
  display_name: string | null
  target_weight: number
  include_in_rebalance: boolean
  is_active: boolean
}

export interface TransactionPayload {
  portfolio_id: number
  instrument_id: number
  account_id: number | null
  cash_account_id: number | null
  date: string
  type: TransactionType
  qty: number
  price: number
  fee: number
  note: string | null
}

export interface Transaction extends TransactionPayload {
  id: number
  instrument_name: string
  instrument_code: string | null
  account_name: string | null
  cash_account_name: string | null
  amount: number
  created_at: string
}

export interface SnapshotHolding {
  user_asset_id: number
  instrument_id: number
  instrument_code: string | null
  instrument_exchange: string | null
  name: string
  bucket_name: string | null
  group_name: string | null
  quantity: number
  cost_basis: number
  average_cost: number
  latest_price: number | null
  market_value: number
}

export interface SnapshotBucket {
  bucket_id: number | null
  name: string
  target_weight: number
  current_value: number
  actual_weight: number
}

export interface PortfolioSnapshot {
  portfolio_id: number
  total_value: number
  holdings_value: number
  cash_value: number
  holdings: SnapshotHolding[]
  cash_accounts: CashAccount[]
  buckets: SnapshotBucket[]
}
