export type InstrumentType = 'stock' | 'fund' | 'etf' | 'bond' | 'gold' | 'crypto'
export type PriceState = 'fresh' | 'stale' | 'missing'
export type TradingPlatformType = 'broker' | 'bank' | 'fund_platform' | 'payment' | 'crypto_exchange' | 'other'

export interface AdminUser {
  email: string
}

export interface AdminLoginResponse {
  access_token: string
  token_type: 'bearer'
  admin: AdminUser
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
  created_at: string
  last_fetched_at: string | null
  latest_price: number | null
  price_date: string | null
}

export interface InstrumentPayload {
  name: string
  type: InstrumentType
  code: string | null
  exchange: string | null
  currency: string
  source: string | null
  is_active: boolean
}

export interface InstrumentSyncResult {
  imported: number
  skipped: number
  errors: string[]
}

export interface TradingPlatform {
  id: number
  name: string
  type: TradingPlatformType
  account_type: string | null
  display_order: number
  is_active: boolean
  created_at: string
}

export interface TradingPlatformPayload {
  name: string
  type: TradingPlatformType
  account_type: string | null
  display_order: number
  is_active: boolean
}

export interface PriceStatus {
  instrument_id: number
  instrument_name: string
  instrument_code: string | null
  instrument_exchange: string | null
  instrument_type: InstrumentType
  latest_price: number | null
  price_date: string | null
  last_fetched_at: string | null
  price_age_days: number | null
  price_state: PriceState
}

export interface PriceFetchResult {
  updated: number
  target_count: number
  errors: string[]
}
