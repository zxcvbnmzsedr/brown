import { Download, Pencil, Plus, RefreshCcw, Save, Trash2, Upload, X } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAssets, useTransactions } from '../api/hooks'
import { AssetSearchPicker } from '../components/AssetSearchPicker'
import type {
  Asset,
  AssetSearchResult,
  CsvImportResult,
  Transaction,
  TransactionPayload,
  TransactionType,
  TransactionUpdate,
} from '../types'
import { formatMoney, formatNumber, today } from '../utils/format'

interface TransactionFormState {
  date: string
  assetId: string
  assetQuery: string
  type: TransactionType
  qty: string
  price: string
  fee: string
  note: string
}

const defaultForm: TransactionFormState = {
  date: today(),
  assetId: '',
  assetQuery: '',
  type: 'buy',
  qty: '',
  price: '',
  fee: '0',
  note: '',
}

export function LedgerPage() {
  const navigate = useNavigate()
  const { data: assets, loading: assetsLoading, refresh: refreshAssets } = useAssets()
  const { data: transactions, loading: txLoading, refresh: refreshTx } = useTransactions()
  const [form, setForm] = useState<TransactionFormState>(defaultForm)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [selectedSearchResult, setSelectedSearchResult] = useState<AssetSearchResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [importResult, setImportResult] = useState<CsvImportResult | null>(null)
  const [importing, setImporting] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const assetList = useMemo(() => assets ?? [], [assets])
  const txList = transactions ?? []
  const loading = assetsLoading || txLoading

  const selectedAsset = useMemo(
    () => assetList.find((asset) => String(asset.id) === form.assetId),
    [assetList, form.assetId],
  )
  const selectedAssetId = selectedAsset?.id ?? null
  const canSubmit = Boolean(selectedAssetId)
  const selectedAssetName = selectedAsset?.name ?? selectedSearchResult?.name ?? null
  const selectedIncludeInPortfolio = selectedAsset?.include_in_portfolio ?? false
  const selectedBadgeLabel = selectedIncludeInPortfolio ? '已纳入组合' : '待归类'
  const showClassifyLink = Boolean(selectedAssetName && !selectedIncludeInPortfolio)
  const searchConfiguredAssets = useMemo(
    () => createConfiguredAssetSearch(assetList),
    [assetList],
  )

  async function refresh() {
    await Promise.all([refreshAssets(), refreshTx()])
  }

  async function submitTransaction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    try {
      const payload: TransactionPayload = {
        date: form.date,
        asset_id: selectedAssetId,
        asset: null,
        type: form.type,
        qty: Number(form.qty),
        price: Number(form.price),
        fee: Number(form.fee || 0),
        note: form.note.trim() || null,
      }
      let savedTransaction: Transaction
      if (editingId) {
        const updatePayload: TransactionUpdate = {
          date: payload.date,
          asset_id: payload.asset_id ?? undefined,
          type: payload.type,
          qty: payload.qty,
          price: payload.price,
          fee: payload.fee,
          note: payload.note,
        }
        savedTransaction = await api.updateTransaction(editingId, updatePayload)
      } else {
        savedTransaction = await api.createTransaction(payload)
      }
      setForm({
        ...defaultForm,
        assetId: String(savedTransaction.asset_id),
        assetQuery: savedTransaction.asset_name,
      })
      setSelectedSearchResult(null)
      setEditingId(null)
      await refresh()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '操作失败')
    }
  }

  function startEdit(tx: Transaction) {
    setEditingId(tx.id)
    setForm({
      date: tx.date,
      assetId: String(tx.asset_id),
      assetQuery: tx.asset_name,
      type: tx.type,
      qty: String(tx.qty),
      price: String(tx.price),
      fee: String(tx.fee),
      note: tx.note ?? '',
    })
    setSelectedSearchResult(null)
  }

  function cancelEdit() {
    setEditingId(null)
    setSelectedSearchResult(null)
    setForm({ ...defaultForm, assetId: form.assetId, assetQuery: selectedAsset?.name ?? '' })
  }

  function handleAssetQueryChange(nextQuery: string) {
    setSelectedSearchResult(null)
    setForm((current) => ({ ...current, assetQuery: nextQuery, assetId: '' }))
  }

  function selectAssetResult(result: AssetSearchResult) {
    setSelectedSearchResult(result)
    setForm((current) => ({
      ...current,
      assetId: String(result.existing_asset_id),
      assetQuery: result.name,
      price:
        result.latest_price !== null && result.latest_price !== undefined
          ? String(result.latest_price)
          : current.price,
    }))
  }

  async function deleteTransaction(id: number) {
    setError(null)
    try {
      await api.deleteTransaction(id)
      await refresh()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '删除失败')
    }
  }

  function handleExport() {
    window.open(api.exportTransactions(), '_blank')
  }

  async function handleImport(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setImporting(true)
    setImportResult(null)
    setError(null)
    try {
      const result = await api.importTransactions(file)
      setImportResult(result)
      await refresh()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '导入失败')
    } finally {
      setImporting(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <>
      <header className="topbar">
        <div>
          <h1>交易账单</h1>
          <p>录入买入/卖出交易，支持编辑和删除。</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="ghost-button" type="button" onClick={() => void refresh()}>
            <RefreshCcw size={16} className={loading ? 'spin' : ''} />
            刷新
          </button>
          <button className="ghost-button" type="button" onClick={handleExport}>
            <Download size={16} />
            导出 CSV
          </button>
          <button className="ghost-button" type="button" disabled={importing} onClick={() => fileInputRef.current?.click()}>
            <Upload size={16} />
            {importing ? '导入中...' : '导入 CSV'}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            style={{ display: 'none' }}
            onChange={(e) => void handleImport(e)}
          />
        </div>
      </header>

      {importResult && (
        <div className="alert" style={{ borderColor: '#22c55e' }}>
          成功导入 {importResult.imported} 条记录。
          {importResult.errors.length > 0 && (
            <> ({importResult.errors.length} 个错误: {importResult.errors.join('; ')})</>
          )}
        </div>
      )}

      {error && <div className="alert">{error}</div>}

      <div className="two-column-page">
        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>{editingId ? '编辑交易' : '录入交易'}</h2>
              <p>卖出数量不能超过当前已持有数量。</p>
            </div>
          </div>
          <form className="form-grid" onSubmit={submitTransaction}>
            <label>
              日期
              <input
                required
                type="date"
                value={form.date}
                onChange={(event) => setForm((current) => ({ ...current, date: event.target.value }))}
              />
            </label>
            <label>
              标的
              <AssetSearchPicker
                value={form.assetQuery}
                selectedName={selectedAssetName}
                search={searchConfiguredAssets}
                onValueChange={handleAssetQueryChange}
                onSelect={selectAssetResult}
              />
              {selectedAsset || selectedSearchResult ? (
                <div className="selected-asset-card">
                  <div>
                    <strong>{selectedAsset?.name ?? selectedSearchResult?.name}</strong>
                    <span>
                      {selectedAsset?.code ?? selectedSearchResult?.code ?? '无代码'} · {selectedAsset?.exchange ?? selectedSearchResult?.exchange ?? '未识别市场'}
                    </span>
                  </div>
                  <div className="selected-asset-card-actions">
                    <span className={`status-dot ${selectedIncludeInPortfolio ? 'status-on' : 'status-warning'}`}>
                      {selectedBadgeLabel}
                    </span>
                    {showClassifyLink ? (
                      <button
                        className="ghost-button compact-button"
                        type="button"
                        onClick={() => navigate('/assets')}
                      >
                        去配置页归类
                      </button>
                    ) : null}
                  </div>
                </div>
              ) : null}
            </label>
            <label>
              类型
              <select
                value={form.type}
                onChange={(event) =>
                  setForm((current) => ({ ...current, type: event.target.value as TransactionType }))
                }
              >
                <option value="buy">买入</option>
                <option value="sell">卖出</option>
              </select>
            </label>
            <label>
              数量
              <input
                required
                min="0"
                step="0.0001"
                type="number"
                value={form.qty}
                onChange={(event) => setForm((current) => ({ ...current, qty: event.target.value }))}
              />
            </label>
            <label>
              单价
              <input
                required
                min="0"
                step="0.0001"
                type="number"
                value={form.price}
                onChange={(event) => setForm((current) => ({ ...current, price: event.target.value }))}
              />
            </label>
            <label>
              手续费
              <input
                min="0"
                step="0.01"
                type="number"
                value={form.fee}
                onChange={(event) => setForm((current) => ({ ...current, fee: event.target.value }))}
              />
            </label>
            <label className="full-width">
              备注
              <input
                value={form.note}
                onChange={(event) => setForm((current) => ({ ...current, note: event.target.value }))}
                placeholder="建仓 / 定投 / 再平衡"
              />
            </label>
            <div className="form-actions">
              <button className="primary-button" disabled={!canSubmit} type="submit">
                {editingId ? <Save size={16} /> : <Plus size={16} />}
                {editingId ? '保存修改' : '录入交易'}
              </button>
              {editingId && (
                <button className="ghost-button" type="button" onClick={cancelEdit}>
                  <X size={16} />
                  取消
                </button>
              )}
            </div>
          </form>
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>交易账单</h2>
              <p>所有交易按日期倒序展示。</p>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>日期</th>
                  <th>标的</th>
                  <th>方向</th>
                  <th>数量</th>
                  <th>单价</th>
                  <th>手续费</th>
                  <th>备注</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {txList.map((tx) => (
                  <tr key={tx.id}>
                    <td>{tx.date}</td>
                    <td><strong>{tx.asset_name}</strong></td>
                    <td>
                      <span className={`pill ${tx.type === 'buy' ? 'pill-buy' : 'pill-sell'}`}>
                        {tx.type === 'buy' ? '买入' : '卖出'}
                      </span>
                    </td>
                    <td>{formatNumber(tx.qty)}</td>
                    <td>{formatMoney(tx.price)}</td>
                    <td>{formatMoney(tx.fee)}</td>
                    <td>{tx.note || '-'}</td>
                    <td>
                      <div className="row-actions">
                        <button
                          className="icon-button"
                          type="button"
                          aria-label={`编辑 ${tx.asset_name} ${tx.date} 交易`}
                          onClick={() => startEdit(tx)}
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          className="icon-button danger-button"
                          type="button"
                          aria-label={`删除 ${tx.asset_name} ${tx.date} 交易`}
                          onClick={() => void deleteTransaction(tx.id)}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {txList.length === 0 && (
                  <tr>
                    <td colSpan={8}>暂无交易记录。</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </>
  )
}

function createConfiguredAssetSearch(assets: Asset[]) {
  return async (query: string): Promise<AssetSearchResult[]> => {
    const normalizedQuery = query.trim().toLowerCase()
    if (!normalizedQuery) {
      return []
    }

    return assets
      .filter((asset) =>
        [asset.name, asset.code, asset.exchange, asset.platform]
          .filter(Boolean)
          .some((value) => value!.toLowerCase().includes(normalizedQuery)),
      )
      .slice(0, 20)
      .map(assetToSearchResult)
  }
}

function assetToSearchResult(asset: Asset): AssetSearchResult {
  return {
    id: `local:${asset.id}`,
    source: 'local',
    existing_asset_id: asset.id,
    name: asset.name,
    type: asset.type,
    code: asset.code,
    exchange: asset.exchange,
    platform: asset.platform,
    latest_price: asset.latest_price,
    include_in_portfolio: asset.include_in_portfolio,
    group_name: asset.group_name,
    bucket_name: asset.bucket_name,
  }
}
