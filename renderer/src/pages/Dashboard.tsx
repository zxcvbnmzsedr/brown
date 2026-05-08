import { AlertTriangle, CheckCircle2, Clock3, PieChart, RefreshCcw, Target, WalletCards } from 'lucide-react'
import { AllocationRing } from '../components/AllocationRing'
import { MetricCard } from '../components/MetricCard'
import { usePriceFetch, useSnapshot } from '../api/hooks'
import type { MonitorState, PriceState } from '../types'
import { formatDateTime, formatMoney, formatNumber, formatPercent } from '../utils/format'

const STATUS_TEXT: Record<MonitorState, string> = {
  ok: '当前无需操作',
  watch: '进入观察区',
  warning: '接近再平衡区',
  rebalance: '需要再平衡',
  incomplete: '价格数据不完整',
}

const PRICE_TEXT: Record<PriceState, string> = {
  cash: '现金',
  fresh: '已更新',
  stale: '已过期',
  missing: '缺价格',
}

export function Dashboard() {
  const { data: snapshot, loading, refresh } = useSnapshot()
  const { fetchAll, loading: priceLoading, result: priceResult } = usePriceFetch()

  const items = snapshot?.items ?? []
  const allItems = snapshot?.all_items ?? items
  const buckets = snapshot?.buckets ?? []
  const monitorState = snapshot?.price_state === 'incomplete'
    ? 'incomplete'
    : buckets.reduce<MonitorState>((state, bucket) => rankState(state, bucket.monitor_state), 'ok')
  const issueBuckets = buckets.filter((bucket) => bucket.monitor_state !== 'ok')
  const latestFetchedAt = latestPriceFetchedAt(items.map((item) => item.price_fetched_at))

  async function handleFetchPrices() {
    await fetchAll()
    await refresh()
  }

  return (
    <>
      <header className="topbar">
        <div>
          <h1>组合总览</h1>
          <p>本地记录交易，按永久组合纪律监控四大资产桶。</p>
        </div>
        <div className="topbar-actions">
          <button className="ghost-button" type="button" onClick={() => void handleFetchPrices()} disabled={priceLoading}>
            <RefreshCcw size={16} className={priceLoading ? 'spin' : ''} />
            抓取价格
          </button>
          <button className="ghost-button" type="button" onClick={() => void refresh()}>
            <RefreshCcw size={16} className={loading ? 'spin' : ''} />
            刷新
          </button>
        </div>
      </header>

      {priceResult ? (
        <div className={`alert ${priceResult.errors.length ? '' : 'alert-success'}`}>
          已更新 {priceResult.updated} 个标的{priceResult.errors.length ? `，${priceResult.errors.join('；')}` : '。'}
        </div>
      ) : null}

      <div className="page-grid">
        <section className={`panel monitor-banner monitor-${monitorState}`}>
          <div className="status-icon">
            {monitorState === 'ok' ? <CheckCircle2 size={28} /> : <AlertTriangle size={28} />}
          </div>
          <div>
            <h2>{STATUS_TEXT[monitorState]}</h2>
            <p>{buildMonitorMessage(monitorState, issueBuckets.length, snapshot?.missing_price_count ?? 0, snapshot?.stale_price_count ?? 0)}</p>
          </div>
        </section>

        <div className="metrics-grid">
          <MetricCard
            icon={WalletCards}
            label="全部持仓"
            value={formatMoney(snapshot?.total_holdings_value ?? snapshot?.total_value ?? 0)}
          />
          <MetricCard
            icon={PieChart}
            label="永久组合资产"
            value={formatMoney(snapshot?.total_value ?? 0)}
          />
          <MetricCard
            icon={Target}
            label="目标配置合计"
            value={formatPercent(snapshot?.target_weight_total ?? 0)}
            tone={(snapshot?.target_weight_total ?? 0) === 1 ? 'good' : 'warn'}
          />
          <MetricCard
            icon={Clock3}
            label="最近价格更新"
            value={latestFetchedAt ? formatDateTime(latestFetchedAt) : '-'}
            tone={snapshot?.price_state === 'incomplete' ? 'warn' : 'good'}
          />
        </div>

        {(snapshot?.pending_classification_count ?? 0) > 0 ? (
          <section className="panel monitor-banner monitor-watch">
            <div className="status-icon">
              <AlertTriangle size={28} />
            </div>
            <div>
              <h2>有待归类标的</h2>
              <p>
                {snapshot?.pending_classification_count} 个标的暂未纳入永久组合，合计
                {formatMoney(snapshot?.pending_classification_value ?? 0)}。这些持仓会进入全部持仓统计，但不会参与纪律区间和再平衡。
              </p>
            </div>
          </section>
        ) : null}

        <section className="panel dashboard-main">
          <div className="section-heading">
            <div>
              <h2>组合快照</h2>
              <p>外圈是实际四大类，内圈是永久组合目标。</p>
            </div>
          </div>
          {snapshot && buckets.length > 0 ? (
            <AllocationRing buckets={buckets} totalValue={snapshot.total_value} />
          ) : (
            <div className="empty-state">录入持仓和交易后，Dashboard 会显示组合快照。</div>
          )}
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>纪律区间</h2>
              <p>经典永久组合按 15% 到 35% 判断是否触发再平衡。</p>
            </div>
          </div>
          <div className="bucket-grid">
            {buckets.map((bucket) => (
              <div className={`bucket-tile bucket-state-${bucket.monitor_state}`} key={bucket.bucket_id}>
                <div className="bucket-title-row">
                  <div>
                    <span>{bucket.name}</span>
                    <strong>{formatMoney(bucket.current_value)}</strong>
                  </div>
                  <span className={`status-dot status-${bucket.monitor_state}`}>{STATUS_TEXT[bucket.monitor_state]}</span>
                </div>
                <div className="bucket-meter" aria-hidden="true">
                  <span style={{ width: `${Math.min(bucket.actual_weight * 100, 100)}%` }} />
                </div>
                <footer>
                  <span>实际 {formatPercent(bucket.actual_weight)}</span>
                  <span>目标 {formatPercent(bucket.target_weight)}</span>
                  <span>
                    区间 {formatPercent(bucket.lower_bound)} - {formatPercent(bucket.upper_bound)}
                  </span>
                  <span className={bucket.monitor_state === 'rebalance' ? 'danger-text' : ''}>
                    {distanceText(bucket.distance_to_lower, bucket.distance_to_upper)}
                  </span>
                </footer>
              </div>
            ))}
          </div>
        </section>

        {(snapshot?.missing_price_count || snapshot?.stale_price_count) ? (
          <section className="panel">
            <div className="section-heading">
              <div>
                <h2>价格数据</h2>
                <p>缺失或过期价格会阻止交易清单生成。</p>
              </div>
            </div>
            <div className="price-warning-list">
              {items
                .filter((item) => item.quantity > 0 && (item.price_state === 'missing' || item.price_state === 'stale'))
                .map((item) => (
                  <span className="price-warning-chip" key={item.asset_id}>
                    {item.name} {PRICE_TEXT[item.price_state]}
                    {item.price_age_days !== null ? ` ${item.price_age_days} 天` : ''}
                  </span>
                ))}
            </div>
          </section>
        ) : null}

        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>全部持仓明细</h2>
              <p>待归类标的只进入全部持仓，不参与永久组合再平衡。</p>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>资产层级</th>
                  <th>标的</th>
                  <th>数量</th>
                  <th>当前价格</th>
                  <th>价格状态</th>
                  <th>当前市值</th>
                  <th>实际占比</th>
                </tr>
              </thead>
              <tbody>
                {allItems.map((item) => (
                  <tr key={item.asset_id}>
                    <td>
                      <strong>{item.bucket_name ?? '未归类'}</strong>
                      <span className="subtle">
                        {item.include_in_portfolio ? item.group_name ?? '未设置细则' : '待归类，不参与再平衡'}
                      </span>
                    </td>
                    <td>
                      <strong>{item.name}</strong>
                      <span className="subtle">{item.platform || item.code || item.type}</span>
                    </td>
                    <td>{formatNumber(item.quantity)}</td>
                    <td>{formatMoney(item.current_price)}</td>
                    <td>
                      <span className={`status-dot price-${item.price_state}`}>
                        {PRICE_TEXT[item.price_state]}
                      </span>
                      <span className="subtle">{item.price_date ?? '-'}</span>
                    </td>
                    <td>{formatMoney(item.current_value)}</td>
                    <td>{formatPercent(item.actual_weight)}</td>
                  </tr>
                ))}
                {allItems.length === 0 && (
                  <tr>
                    <td colSpan={7}>暂无持仓数据。</td>
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

function rankState(current: MonitorState, next: MonitorState): MonitorState {
  const rank: Record<MonitorState, number> = { ok: 0, watch: 1, warning: 2, rebalance: 3, incomplete: 4 }
  return rank[next] > rank[current] ? next : current
}

function latestPriceFetchedAt(values: Array<string | null>): string | null {
  const dates = values
    .filter((value): value is string => Boolean(value))
    .sort((a, b) => new Date(b).getTime() - new Date(a).getTime())
  return dates[0] ?? null
}

function buildMonitorMessage(state: MonitorState, issueCount: number, missingCount: number, staleCount: number): string {
  if (state === 'incomplete') {
    return `有 ${missingCount} 个标的缺少价格、${staleCount} 个标的价格过期，先补齐价格再判断交易。`
  }
  if (state === 'rebalance') {
    return `${issueCount} 个资产桶触发纪律区间，需要进入再平衡操作台确认。`
  }
  if (state === 'warning') {
    return `${issueCount} 个资产桶偏离较大，建议关注但不必立刻交易。`
  }
  if (state === 'watch') {
    return `${issueCount} 个资产桶轻微偏离，继续观察。`
  }
  return '四大资产桶都在纪律区间内。'
}

function distanceText(distanceToLower: number | null, distanceToUpper: number | null): string {
  if (distanceToLower === null || distanceToUpper === null) {
    return '区间未设置'
  }
  if (distanceToLower < 0) {
    return `低于下限 ${formatPercent(Math.abs(distanceToLower))}`
  }
  if (distanceToUpper < 0) {
    return `超过上限 ${formatPercent(Math.abs(distanceToUpper))}`
  }
  return `距边界 ${formatPercent(Math.min(distanceToLower, distanceToUpper))}`
}
