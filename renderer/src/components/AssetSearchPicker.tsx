import { Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { AssetSearchResult } from '../types'
import { formatMoney } from '../utils/format'

type SearchStatus = 'idle' | 'loading' | 'success' | 'error'

interface AssetSearchPickerProps {
  value: string
  onValueChange: (value: string) => void
  onSelect: (result: AssetSearchResult) => void
  search?: (query: string) => Promise<AssetSearchResult[]>
  selectedName?: string | null
  autoFocus?: boolean
  disabled?: boolean
  placeholder?: string
  minQueryLength?: number
  debounceMs?: number
  className?: string
}

export function AssetSearchPicker({
  value,
  onValueChange,
  onSelect,
  search = api.searchAssets,
  selectedName = null,
  autoFocus = false,
  disabled = false,
  placeholder = '输入代码或名称',
  minQueryLength = 2,
  debounceMs = 350,
  className,
}: AssetSearchPickerProps) {
  const [results, setResults] = useState<AssetSearchResult[]>([])
  const [status, setStatus] = useState<SearchStatus>('idle')
  const [error, setError] = useState<string | null>(null)

  const query = value.trim()
  const shouldSearch = !disabled && query.length >= minQueryLength && selectedName !== query

  useEffect(() => {
    if (!shouldSearch) {
      return
    }

    let ignore = false
    const timer = window.setTimeout(() => {
      void search(query)
        .then((nextResults) => {
          if (ignore) return
          setResults(nextResults)
          setError(null)
          setStatus('success')
        })
        .catch((caught) => {
          if (ignore) return
          setResults([])
          setError(caught instanceof Error ? caught.message : '标的搜索失败')
          setStatus('error')
        })
    }, debounceMs)

    return () => {
      ignore = true
      window.clearTimeout(timer)
    }
  }, [debounceMs, query, search, shouldSearch])

  function handleValueChange(nextValue: string) {
    onValueChange(nextValue)
    setError(null)
    if (nextValue.trim().length < minQueryLength) {
      setResults([])
      setStatus('idle')
      return
    }
    setStatus('loading')
  }

  function handleSelect(result: AssetSearchResult) {
    setResults([])
    setStatus('idle')
    setError(null)
    onSelect(result)
  }

  const showPanel = status === 'loading' || status === 'error' || status === 'success'
  const rootClassName = className ? `asset-search-picker ${className}` : 'asset-search-picker'

  return (
    <div className={rootClassName}>
      <div className="asset-search-field">
        <Search size={16} aria-hidden="true" />
        <input
          required
          autoFocus={autoFocus}
          disabled={disabled}
          value={value}
          placeholder={placeholder}
          onChange={(event) => handleValueChange(event.target.value)}
        />
      </div>

      {showPanel ? (
        <div className="asset-search-results">
          {status === 'loading' ? <div className="asset-search-empty">搜索中...</div> : null}
          {status === 'error' ? <div className="asset-search-empty">{error}</div> : null}
          {status === 'success' && results.length === 0 ? (
            <div className="asset-search-empty">未找到匹配标的。</div>
          ) : null}
          {results.map((result) => (
            <button type="button" key={result.id} onClick={() => handleSelect(result)}>
              <span>
                <strong>{result.name}</strong>
                <small>{assetResultDescription(result)}</small>
              </span>
              <span className="subtle">
                {result.latest_price !== null && result.latest_price !== undefined
                  ? formatMoney(result.latest_price)
                  : '无价格'}
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function assetResultDescription(result: AssetSearchResult): string {
  const market = [result.code ?? '无代码', result.exchange ?? '未识别市场'].join(' · ')
  const source = result.source === 'local' ? '本地标的' : 'AKShare'
  const location = result.group_name
    ? ` · ${result.bucket_name ?? '未分大类'} / ${result.group_name}`
    : ''
  return `${market} · ${source}${location}`
}
