import { Plus, Save, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../../api/client'
import { AssetSearchPicker } from '../../components/AssetSearchPicker'
import type { Asset, AssetPayload, AssetSearchResult } from '../../types'
import { formatMoney } from '../../utils/format'

export interface AssetCreateTarget {
  groupId: number | null
  includeInPortfolio: boolean
  label: string
}

interface AssetCreateFormProps {
  target: AssetCreateTarget
  assets: Asset[]
  onSaved: () => Promise<void>
  onCancel: () => void
}

export function AssetCreateForm({ target, assets, onSaved, onCancel }: AssetCreateFormProps) {
  const [query, setQuery] = useState('')
  const [selectedResult, setSelectedResult] = useState<AssetSearchResult | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const matchedAsset = useMemo(
    () => (selectedResult ? findMatchingAsset(assets, selectedResult) : null),
    [assets, selectedResult],
  )

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedResult) return

    setSubmitting(true)
    setError(null)
    try {
      if (matchedAsset) {
        if (!confirmMove(matchedAsset, target)) {
          return
        }
        const updated = await api.updateAsset(
          matchedAsset.id,
          assetPayload(matchedAsset, {
            group_id: target.groupId,
            include_in_portfolio: target.includeInPortfolio,
            is_active: true,
          }),
        )
        await syncLatestPrice(updated.id, selectedResult.latest_price)
      } else if (selectedResult.existing_asset_id) {
        throw new Error('本地标的列表未同步，请刷新后重试')
      } else {
        const created = await api.createAsset({
          group_id: target.groupId,
          name: selectedResult.name,
          platform: selectedResult.platform ?? 'AKShare',
          type: selectedResult.type,
          code: selectedResult.code,
          exchange: selectedResult.exchange,
          target_weight: 0,
          is_active: true,
          include_in_portfolio: target.includeInPortfolio,
        })
        await syncLatestPrice(created.id, selectedResult.latest_price)
      }

      await onSaved()
      onCancel()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '新增标的失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="asset-create-form" onSubmit={submit}>
      <div className="asset-create-context">
        <span>{target.includeInPortfolio ? '新增到细则' : '新增到暂存区'}</span>
        <strong>{target.label}</strong>
      </div>

      <AssetSearchPicker
        value={query}
        selectedName={selectedResult?.name}
        autoFocus
        onValueChange={(nextValue) => {
          setQuery(nextValue)
          setSelectedResult(null)
          setError(null)
        }}
        onSelect={(result) => {
          setSelectedResult(result)
          setQuery(result.name)
          setError(null)
        }}
      />

      {selectedResult ? (
        <div className="selected-asset-card">
          <div>
            <strong>{selectedResult.name}</strong>
            <span>
              {selectedResult.code ?? '无代码'} · {selectedResult.exchange ?? '未识别市场'} · 最新价{' '}
              {formatMoney(selectedResult.latest_price)}
            </span>
          </div>
          <span className={`status-dot ${matchedAsset ? assetStatusClass(matchedAsset) : 'status-warning'}`}>
            {selectedResultLabel(matchedAsset, target)}
          </span>
        </div>
      ) : null}

      {error ? <div className="asset-create-error">{error}</div> : null}

      <div className="asset-create-actions">
        <button className="primary-button compact-button" type="submit" disabled={!selectedResult || submitting}>
          {submitting ? <Save size={14} /> : <Plus size={14} />}
          {submitting ? '提交中...' : '提交'}
        </button>
        <button className="ghost-button compact-button" type="button" onClick={onCancel}>
          <X size={14} />
          取消
        </button>
      </div>
    </form>
  )
}

function findMatchingAsset(assets: Asset[], result: AssetSearchResult): Asset | null {
  if (result.existing_asset_id) {
    return assets.find((asset) => asset.id === result.existing_asset_id) ?? null
  }

  if (result.code) {
    return (
      assets.find(
        (asset) =>
          asset.code === result.code &&
          (asset.exchange ?? null) === (result.exchange ?? null),
      ) ?? null
    )
  }

  return assets.find((asset) => asset.name === result.name) ?? null
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

async function syncLatestPrice(assetId: number, price: number | null) {
  if (price === null || price === undefined || price <= 0) {
    return
  }
  await api.updatePrice(assetId, { price })
}

function confirmMove(asset: Asset, target: AssetCreateTarget): boolean {
  const alreadyInTarget =
    asset.include_in_portfolio === target.includeInPortfolio && asset.group_id === target.groupId
  if (alreadyInTarget) {
    return true
  }

  if (asset.include_in_portfolio && asset.group_name) {
    const currentLocation = [asset.bucket_name, asset.group_name].filter(Boolean).join(' / ')
    const action = target.includeInPortfolio ? `移动到 ${target.label}` : '移至未纳入组合'
    return window.confirm(`标的已在 ${currentLocation}，是否${action}？`)
  }

  return true
}

function assetStatusClass(asset: Asset): string {
  if (!asset.is_active) return 'status-inactive'
  if (!asset.include_in_portfolio) return 'status-watch'
  if (!asset.group_id) return 'status-warning'
  return 'status-on'
}

function selectedResultLabel(asset: Asset | null, target: AssetCreateTarget): string {
  if (!asset) {
    return target.includeInPortfolio ? 'AKShare 新标的' : '将存入暂存区'
  }
  if (asset.include_in_portfolio && asset.group_name) {
    return `${asset.group_name} 细则`
  }
  return '暂存区已有'
}
