export type MarketScope = 'cn' | 'hk' | 'us'

export interface MarketOption {
  value: MarketScope
  label: string
  shortLabel: string
}

export const DEFAULT_MARKET: MarketScope = 'cn'
export const MARKET_STORAGE_KEY = 'stock-pilot.market-scope'

export const MARKET_OPTIONS: MarketOption[] = [
  { value: 'cn', label: 'A股（沪深）', shortLabel: 'A股' },
  { value: 'hk', label: '港股', shortLabel: '港股' },
  { value: 'us', label: '美股', shortLabel: '美股' },
]

export function normalizeMarket(value: string | null | undefined): MarketScope {
  if (value === 'hk' || value === 'us') {
    return value
  }
  return DEFAULT_MARKET
}

export function readStoredMarket(): MarketScope {
  if (typeof window === 'undefined') {
    return DEFAULT_MARKET
  }
  return normalizeMarket(window.localStorage.getItem(MARKET_STORAGE_KEY))
}

export function writeStoredMarket(value: MarketScope) {
  if (typeof window === 'undefined') {
    return
  }
  window.localStorage.setItem(MARKET_STORAGE_KEY, value)
}

export function marketLabel(value: MarketScope) {
  return MARKET_OPTIONS.find((item) => item.value === value)?.label ?? 'A股（沪深）'
}
