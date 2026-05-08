import { AlertTriangle, Archive, CheckCircle2, MoveUp, RefreshCcw, Settings } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { usePriceFetch, useRebalancePlan, useSnapshot } from '../api/hooks'
import type { AssetAction, FetchResult, MonitorState, RebalanceConfig } from '../types'
import { formatMoney, formatNumber, formatPercent } from '../utils/format'

export function RebalancePage() {
  const { data: plan, loading: planLoading, refresh: refreshPlan } = useRebalancePlan()
  const { data: snapshot, refresh: refreshSnapshot } = useSnapshot()
  const { fetchAll, loading: priceLoading } = usePriceFetch()
  const [showConfig, setShowConfig] = useState(false)
  const [config, setConfig] = useState<RebalanceConfig | null>(null)
  const [archiveMessage, setArchiveMessage] = useState<string | null>(null)
  const [priceResult, setPriceResult] = useState<FetchResult | null>(null)
  const [archiveLoading, setArchiveLoading] = useState(false)
  const notifiedKeyRef = useRef<string | null>(null)

  async function loadConfig() {
    const c = await api.getRebalanceConfig()
    setConfig(c)
    setShowConfig(true)
  }

  async function saveConfig() {
    if (!config) return
    await api.updateRebalanceConfig(config)
    setShowConfig(false)
    await refreshPlan()
  }

  async function handleRefresh() {
    await Promise.all([refreshPlan(), refreshSnapshot()])
  }

  async function handleFetchPrices() {
    const result = await fetchAll()
    setPriceResult(result)
    await handleRefresh()
  }

  async function archiveCurrentPlan() {
    setArchiveLoading(true)
    setArchiveMessage(null)
    try {
      await api.recordRebalanceFromPlan()
      setArchiveMessage('已保存到再平衡记录。')
    } catch (caught) {
      setArchiveMessage(caught instanceof Error ? caught.message : '保存失败')
    } finally {
      setArchiveLoading(false)
    }
  }

  useEffect(() => {
    if (!plan || plan.status !== 'rebalance' || !window.electronAPI) return
    const key = plan.trigger_reasons.join('|') || `${plan.as_of}-${plan.status}`
    if (key === notifiedKeyRef.current) return
    notifiedKeyRef.current = key
    void window.electronAPI.notifyRebalance(plan.status_label, plan.trigger_reasons.join('; ') || plan.status_message)
  }, [plan])

  const buckets = snapshot?.buckets ?? []
  const tradeList = plan?.trade_list ?? []
  const sellActions = tradeList.filter((a) => a.action === 'sell')
  const buyActions = tradeList.filter((a) => a.action === 'buy')
  const status = plan?.status ?? 'ok'

  return (
    <>
      <header className="topbar">
        <div>
          <h1>再平衡操作台</h1>
          <p>按观察、提醒和 35/15 再平衡区间分层处理。</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="ghost-button" type="button" onClick={() => void handleFetchPrices()} disabled={priceLoading}>
            <RefreshCcw size={16} className={priceLoading ? 'spin' : ''} />
            抓取价格
          </button>
          <button className="ghost-button" type="button" onClick={loadConfig}>
            <Settings size={16} />
            配置
          </button>
          <button className="ghost-button" type="button" onClick={() => void handleRefresh()}>
            <RefreshCcw size={16} className={planLoading ? 'spin' : ''} />
            刷新
          </button>
        </div>
      </header>

      {priceResult ? (
        <div className={`alert ${priceResult.errors.length ? '' : 'alert-success'}`}>
          已更新 {priceResult.updated} 个标的{priceResult.errors.length ? `，${priceResult.errors.join('；')}` : '。'}
        </div>
      ) : null}

      {showConfig && config && (
        <section className="panel">
          <div className="section-heading">
            <h2>再平衡配置</h2>
          </div>
          <div className="form-grid">
            <label>
              模式
              <select
                value={config.mode}
                onChange={(e) => setConfig({ ...config, mode: e.target.value as RebalanceConfig['mode'] })}
              >
                <option value="classic_35_15">经典 35/15 法则</option>
                <option value="custom">自定义阈值</option>
              </select>
            </label>
            <label>
              观察偏离
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={config.watch_drift}
                onChange={(e) => setConfig({ ...config, watch_drift: Number(e.target.value) })}
              />
            </label>
            <label>
              提醒偏离
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={config.warning_drift}
                onChange={(e) => setConfig({ ...config, warning_drift: Number(e.target.value) })}
              />
            </label>
            <label>
              价格有效天数
              <input
                type="number"
                step="1"
                min="0"
                max="365"
                value={config.max_price_age_days}
                onChange={(e) => setConfig({ ...config, max_price_age_days: Number(e.target.value) })}
              />
            </label>
            <label>
              上限阈值
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={config.upper_threshold}
                onChange={(e) => setConfig({ ...config, upper_threshold: Number(e.target.value) })}
              />
            </label>
            <label>
              下限阈值
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={config.lower_threshold}
                onChange={(e) => setConfig({ ...config, lower_threshold: Number(e.target.value) })}
              />
            </label>
            <div className="form-actions">
              <button className="primary-button" type="button" onClick={() => void saveConfig()}>
                保存配置
              </button>
              <button className="ghost-button" type="button" onClick={() => setShowConfig(false)}>
                取消
              </button>
            </div>
          </div>
        </section>
      )}

      <div className="page-grid">
        <section className={`panel rebalance-status monitor-${status}`}>
          <div className="status-icon">
            {status === 'ok' ? <CheckCircle2 size={28} /> : status === 'rebalance' ? <MoveUp size={28} /> : <AlertTriangle size={28} />}
          </div>
          <div>
            <h2>{plan?.status_label ?? '当前无需再平衡'}</h2>
            <p>{plan?.status_message ?? '四大资产桶都在纪律区间内。'}</p>
            {plan?.config && (
              <p>
                {plan.config.mode === 'classic_35_15'
                  ? `经典 35/15 法则：${formatPercent(plan.config.lower_threshold)} - ${formatPercent(plan.config.upper_threshold)}`
                  : `自定义区间：${formatPercent(plan.config.lower_threshold)} - ${formatPercent(plan.config.upper_threshold)}`}
              </p>
            )}
          </div>
        </section>

        {plan?.price_warnings.length ? (
          <section className="panel">
            <div className="section-heading">
              <h2>价格提示</h2>
            </div>
            <div className="price-warning-list">
              {plan.price_warnings.map((warning) => (
                <span className="price-warning-chip" key={warning}>{warning}</span>
              ))}
            </div>
          </section>
        ) : null}

        {plan?.trigger_reasons.length ? (
          <section className="panel">
            <div className="section-heading">
              <h2>触发原因</h2>
            </div>
            <ul style={{ margin: 0, paddingLeft: '1.5rem' }}>
              {plan.trigger_reasons.map((reason) => (
                <li key={reason} className="danger-text" style={{ marginBottom: '0.25rem' }}>
                  {reason}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {tradeList.length > 0 && (
          <section className="panel">
            <div className="section-heading">
              <div>
                <h2>交易清单</h2>
                <p>先卖后买，按资产细则拆到具体标的。实际下单前仍需核对账户可交易份额。</p>
              </div>
              <button className="primary-button" type="button" disabled={archiveLoading} onClick={() => void archiveCurrentPlan()}>
                <Archive size={16} />
                {archiveLoading ? '保存中...' : '标记已执行'}
              </button>
            </div>
            {archiveMessage && <div className="alert alert-neutral">{archiveMessage}</div>}
            <TradeTable title="卖出" actions={sellActions} tone="sell" />
            <TradeTable title="买入" actions={buyActions} tone="buy" />
          </section>
        )}

        {tradeList.length === 0 && plan && status !== 'rebalance' && (
          <section className="panel">
            <div className="empty-state">当前状态不需要生成交易清单。</div>
          </section>
        )}

        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>偏离详情</h2>
              <p>各资产大类的实际占比、纪律区间和目标市值。</p>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>资产大类</th>
                  <th>状态</th>
                  <th>实际占比</th>
                  <th>纪律区间</th>
                  <th>偏离</th>
                  <th>当前市值</th>
                  <th>目标市值</th>
                </tr>
              </thead>
              <tbody>
                {plan?.buckets.map((bucket) => (
                  <tr key={bucket.bucket_id}>
                    <td><strong>{bucket.bucket_name}</strong></td>
                    <td><span className={`status-dot status-${bucket.monitor_state}`}>{statusLabel(bucket.monitor_state)}</span></td>
                    <td>{formatPercent(bucket.current_weight)}</td>
                    <td>{formatPercent(bucket.lower_bound)} - {formatPercent(bucket.upper_bound)}</td>
                    <td className={bucket.monitor_state === 'rebalance' ? 'danger-text' : ''}>
                      {formatPercent(bucket.current_weight - bucket.target_weight)}
                    </td>
                    <td>{formatMoney(bucket.current_value)}</td>
                    <td>{formatMoney(bucket.target_value)}</td>
                  </tr>
                )) ?? buckets.map((bucket) => (
                  <tr key={bucket.bucket_id}>
                    <td>{bucket.name}</td>
                    <td><span className={`status-dot status-${bucket.monitor_state}`}>{statusLabel(bucket.monitor_state)}</span></td>
                    <td>{formatPercent(bucket.actual_weight)}</td>
                    <td>{formatPercent(bucket.lower_bound)} - {formatPercent(bucket.upper_bound)}</td>
                    <td className={bucket.monitor_state === 'rebalance' ? 'danger-text' : ''}>
                      {formatPercent(bucket.drift)}
                    </td>
                    <td>{formatMoney(bucket.current_value)}</td>
                    <td>-</td>
                  </tr>
                ))}
                {(plan?.buckets ?? buckets).length === 0 && (
                  <tr>
                    <td colSpan={7}>暂无快照数据。</td>
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

function TradeTable({ title, actions, tone }: { title: string; actions: AssetAction[]; tone: 'buy' | 'sell' }) {
  if (actions.length === 0) return null
  return (
    <>
      <h3 className={tone === 'sell' ? 'danger-text' : 'good-text'} style={{ margin: '1rem 0 0.5rem' }}>
        {title} ({actions.length} 笔)
      </h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>标的</th>
              <th>代码</th>
              <th>当前持仓</th>
              <th>{title}份数</th>
              <th>当前价格</th>
              <th>估算金额</th>
            </tr>
          </thead>
          <tbody>
            {actions.map((action) => (
              <tr key={action.asset_id}>
                <td><strong>{action.asset_name}</strong></td>
                <td>{action.asset_code || '-'}</td>
                <td>{formatNumber(action.current_qty)}</td>
                <td className={tone === 'sell' ? 'danger-text' : 'good-text'}>
                  {formatNumber(action.suggested_shares ?? 0)}
                </td>
                <td>{formatMoney(action.current_price)}</td>
                <td>{formatMoney(action.estimated_trade_amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

function statusLabel(status: MonitorState): string {
  return {
    ok: '正常',
    watch: '观察',
    warning: '提醒',
    rebalance: '再平衡',
    incomplete: '不完整',
  }[status]
}
