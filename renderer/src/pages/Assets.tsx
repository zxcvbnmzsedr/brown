import { RefreshCcw } from 'lucide-react'
import { useMemo, useState } from 'react'
import { api } from '../api/client'
import { useAssets, usePriceFetch, useStructure } from '../api/hooks'
import { StructureTab } from './assets/StructureTab'
import { SummaryTiles } from './assets/SummaryTiles'
import type { Asset, AssetPayload, FetchResult } from '../types'

export function AssetsPage() {
  const { data: structure, refresh: refreshStructure } = useStructure()
  const { data: assets, refresh: refreshAssets } = useAssets()
  const { fetchAll, loading: priceLoading } = usePriceFetch()

  const structureList = useMemo(() => structure ?? [], [structure])
  const assetList = useMemo(() => assets ?? [], [assets])

  const [error, setError] = useState<string | null>(null)
  const [priceResult, setPriceResult] = useState<FetchResult | null>(null)

  async function refreshAll() {
    await Promise.all([refreshStructure(), refreshAssets()])
  }

  async function fetchPrices() {
    setError(null)
    try {
      const result = await fetchAll()
      setPriceResult(result)
      await refreshAll()
    } catch (caught) {
      setPriceResult(null)
      setError(caught instanceof Error ? caught.message : '抓取价格失败')
    }
  }

  async function runMutation(task: () => Promise<unknown>) {
    setError(null)
    try {
      await task()
      await refreshAll()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '操作失败')
    }
  }

  function assetPayload(asset: Asset, overrides: Partial<AssetPayload>): AssetPayload {
    return {
      group_id: asset.group_id,
      name: asset.name,
      platform: asset.platform,
      type: asset.type,
      code: asset.code,
      exchange: asset.exchange,
      target_weight: asset.target_weight,
      is_active: asset.is_active,
      include_in_portfolio: asset.include_in_portfolio,
      ...overrides,
    }
  }

  async function updateAsset(asset: Asset, overrides: Partial<AssetPayload>) {
    await runMutation(() => api.updateAsset(asset.id, assetPayload(asset, overrides)))
  }

  async function deleteAsset(asset: Asset) {
    await runMutation(() => api.deleteAsset(asset.id))
  }

  return (
    <>
      <header className="topbar">
        <div>
          <h1>配置管理</h1>
          <p>维护资产大类、细则和标的台账，决定哪些标的参与永久组合。</p>
        </div>
        <div className="topbar-actions">
          <button className="ghost-button" type="button" onClick={() => void fetchPrices()} disabled={priceLoading}>
            <RefreshCcw size={16} className={priceLoading ? 'spin' : ''} />
            抓取价格
          </button>
          <button className="ghost-button" type="button" onClick={() => void refreshAll()}>
            <RefreshCcw size={16} />
            刷新
          </button>
        </div>
      </header>

      {error && <div className="alert">{error}</div>}
      {priceResult ? (
        <div className={`alert ${priceResult.errors.length ? '' : 'alert-success'}`}>
          已更新 {priceResult.updated} 个标的{priceResult.errors.length ? `，${priceResult.errors.join('；')}` : '。'}
        </div>
      ) : null}

      <SummaryTiles structure={structureList} assets={assetList} />

      <div className="config-tab-content">
        <StructureTab
          structure={structureList}
          assets={assetList}
          onAssetChange={updateAsset}
          onAssetDelete={deleteAsset}
          onRefresh={refreshAll}
          onMutate={runMutation}
        />
      </div>
    </>
  )
}
