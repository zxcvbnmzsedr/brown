import { useMemo } from 'react'
import { useRebalanceHistory } from '../api/hooks'
import type { RebalanceHistoryRead } from '../types'
import { formatMoney } from '../utils/format'

function safeJsonParse<T>(raw: string, fallback: T): T {
  try {
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

interface TradeItem {
  asset_id?: number
  asset_name?: string
  action?: string
  quantity?: number
  amount?: number
  [key: string]: unknown
}

export function RebalanceHistoryPage() {
  const { data, loading } = useRebalanceHistory()
  const records: RebalanceHistoryRead[] = data ?? []

  const parsed = useMemo(
    () =>
      records.map((r) => ({
        ...r,
        reasons: safeJsonParse<string[]>(r.trigger_reasons, []),
        trades: safeJsonParse<TradeItem[]>(r.trade_data, []),
      })),
    [records],
  )

  return (
    <>
      <header className="topbar">
        <div>
          <h1>再平衡记录</h1>
          <p>查看历史再平衡执行记录。</p>
        </div>
      </header>

      {loading && <p>加载中...</p>}

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>执行记录</h2>
            <p>共 {records.length} 条记录</p>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>执行时间</th>
                <th>配置模式</th>
                <th>总资产</th>
                <th>触发原因</th>
                <th>交易明细</th>
                <th>备注</th>
              </tr>
            </thead>
            <tbody>
              {parsed.map((r) => (
                <tr key={r.id}>
                  <td>{new Date(r.executed_at).toLocaleString('zh-CN')}</td>
                  <td>{r.config_mode}</td>
                  <td>{formatMoney(r.total_value)}</td>
                  <td>
                    {r.reasons.length > 0 ? (
                      <ul style={{ margin: 0, paddingLeft: 16 }}>
                        {r.reasons.map((reason, i) => (
                          <li key={i}>{reason}</li>
                        ))}
                      </ul>
                    ) : (
                      '-'
                    )}
                  </td>
                  <td>
                    {r.trades.length > 0 ? (
                      <ul style={{ margin: 0, paddingLeft: 16 }}>
                        {r.trades.map((t, i) => (
                          <li key={i}>
                            {t.asset_name ?? `资产#${t.asset_id ?? '?'}`}{' '}
                            {t.action === 'buy' ? '买入' : t.action === 'sell' ? '卖出' : t.action ?? '-'}
                            {t.quantity != null ? ` ${t.quantity} 份` : ''}
                            {t.amount != null ? ` (${formatMoney(t.amount)})` : ''}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      '-'
                    )}
                  </td>
                  <td>{r.note || '-'}</td>
                </tr>
              ))}
              {records.length === 0 && (
                <tr>
                  <td colSpan={6}>暂无再平衡记录。</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}
