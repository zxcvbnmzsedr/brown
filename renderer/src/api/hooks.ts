import { useCallback, useEffect, useRef, useState } from 'react'
import type {
  Asset,
  FetchResult,
  OpeningPosition,
  PortfolioBucket,
  RebalanceHistoryRead,
  RebalancePlanResponse,
  RebalanceResponse,
  Snapshot,
  SnapshotHistoryRead,
  Transaction,
} from '../types'
import { api } from './client'

function useAsyncData<T>(fetcher: () => Promise<T>) {
  const fetcherRef = useRef(fetcher)
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetcherRef.current = fetcher
  }, [fetcher])

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetcherRef.current()
      setData(result)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refresh()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [refresh])

  return { data, loading, error, refresh }
}

export function useStructure() {
  return useAsyncData<PortfolioBucket[]>(api.getStructure)
}

export function useAssets() {
  return useAsyncData<Asset[]>(api.listAssets)
}

export function useTransactions() {
  return useAsyncData<Transaction[]>(api.listTransactions)
}

export function useOpeningPositions() {
  return useAsyncData<OpeningPosition[]>(api.listOpeningPositions)
}

export function useSnapshot() {
  return useAsyncData<Snapshot>(api.getSnapshot)
}

export function useRebalance() {
  return useAsyncData<RebalanceResponse>(api.getRebalance)
}

export function useRebalancePlan() {
  return useAsyncData<RebalancePlanResponse>(api.getRebalancePlan)
}

export function useSnapshotHistory() {
  return useAsyncData<SnapshotHistoryRead[]>(() => api.listSnapshots())
}

export function useRebalanceHistory() {
  return useAsyncData<RebalanceHistoryRead[]>(() => api.listRebalances())
}

export function usePriceFetch() {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<FetchResult | null>(null)

  const fetchAll = useCallback(async () => {
    setLoading(true)
    try {
      const r = await api.fetchAllPrices()
      setResult(r)
      return r
    } finally {
      setLoading(false)
    }
  }, [])

  return { fetchAll, loading, result }
}
