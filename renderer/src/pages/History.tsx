import { Camera } from 'lucide-react'
import { useCallback, useMemo, useRef, useState } from 'react'
import { api } from '../api/client'
import { useSnapshotHistory } from '../api/hooks'
import type { SnapshotHistoryRead } from '../types'
import { formatMoney } from '../utils/format'

const CHART_PADDING = { top: 20, right: 20, bottom: 40, left: 80 }
const CHART_WIDTH = 900
const CHART_HEIGHT = 360

function isValidSnapshot(snapshot: SnapshotHistoryRead | null | undefined): snapshot is SnapshotHistoryRead {
  return Boolean(snapshot && snapshot.recorded_at)
}

export function HistoryPage() {
  const { data, loading, refresh } = useSnapshotHistory()
  const [recording, setRecording] = useState(false)
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  const snapshots = useMemo(() => (data ?? []).filter(isValidSnapshot), [data])

  const latest = snapshots.length > 0 ? snapshots[0] : null

  const chartData = useMemo(() => {
    const sorted = [...snapshots].reverse()
    if (sorted.length === 0) return null

    const values = sorted.map((s) => s.total_value)
    const dates = sorted.map((s) => new Date(s.recorded_at))
    const minVal = Math.min(...values)
    const maxVal = Math.max(...values)
    const valRange = maxVal - minVal || 1
    const minTime = dates[0].getTime()
    const maxTime = dates[dates.length - 1].getTime()
    const timeRange = maxTime - minTime || 1

    const plotW = CHART_WIDTH - CHART_PADDING.left - CHART_PADDING.right
    const plotH = CHART_HEIGHT - CHART_PADDING.top - CHART_PADDING.bottom

    const points = sorted.map((s, i) => {
      const x = CHART_PADDING.left + ((dates[i].getTime() - minTime) / timeRange) * plotW
      const y = CHART_PADDING.top + (1 - (s.total_value - minVal) / valRange) * plotH
      return { x, y, snapshot: s }
    })

    const polylinePoints = points.map((p) => `${p.x},${p.y}`).join(' ')

    const yTicks = 5
    const yLabels = Array.from({ length: yTicks + 1 }, (_, i) => {
      const val = minVal + (valRange * i) / yTicks
      return {
        value: val,
        y: CHART_PADDING.top + (1 - i / yTicks) * plotH,
      }
    })

    const xTickCount = Math.min(sorted.length, 8)
    const xStep = xTickCount > 1 ? Math.max(1, Math.floor((sorted.length - 1) / (xTickCount - 1))) : 1
    const xLabels = Array.from({ length: xTickCount }, (_, i) => {
      const idx = xTickCount === 1 ? 0 : Math.min(i * xStep, sorted.length - 1)
      const d = new Date(sorted[idx].recorded_at)
      return {
        label: `${d.getMonth() + 1}/${d.getDate()}`,
        x: points[idx].x,
      }
    })

    return { points, polylinePoints, yLabels, xLabels }
  }, [snapshots])

  const handleRecord = useCallback(async () => {
    setRecording(true)
    try {
      await api.recordSnapshot()
      await refresh()
    } catch {
      // error handled by refresh
    } finally {
      setRecording(false)
    }
  }, [refresh])

  const hovered = hoveredIndex !== null && chartData ? chartData.points[hoveredIndex] : null

  return (
    <>
      <header className="topbar">
        <div>
          <h1>收益曲线</h1>
          <p>查看总资产变化趋势，记录快照追踪历史。</p>
        </div>
        <button className="primary-button" type="button" disabled={recording} onClick={() => void handleRecord()}>
          <Camera size={16} />
          {recording ? '记录中...' : '记录快照'}
        </button>
      </header>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>总资产</h2>
            <p>{latest ? `最新快照: ${new Date(latest.recorded_at).toLocaleString('zh-CN')}` : '暂无快照数据'}</p>
          </div>
          {latest && <strong className="dashboard-value">{formatMoney(latest.total_value)}</strong>}
        </div>

        {loading && <p>加载中...</p>}

        {!loading && chartData && (
          <div style={{ position: 'relative', width: '100%', overflow: 'auto' }}>
            <svg
              ref={svgRef}
              viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
              style={{ width: '100%', maxWidth: CHART_WIDTH, height: 'auto' }}
              onMouseLeave={() => setHoveredIndex(null)}
            >
              {chartData.yLabels.map((tick) => (
                <g key={tick.y}>
                  <line
                    x1={CHART_PADDING.left}
                    x2={CHART_WIDTH - CHART_PADDING.right}
                    y1={tick.y}
                    y2={tick.y}
                    stroke="#e5e7eb"
                    strokeDasharray="4 4"
                  />
                  <text x={CHART_PADDING.left - 8} y={tick.y + 4} textAnchor="end" fontSize={11} fill="#6b7280">
                    {formatMoney(tick.value)}
                  </text>
                </g>
              ))}

              {chartData.xLabels.map((tick) => (
                <text key={tick.label + tick.x} x={tick.x} y={CHART_HEIGHT - 8} textAnchor="middle" fontSize={11} fill="#6b7280">
                  {tick.label}
                </text>
              ))}

              <polyline
                points={chartData.polylinePoints}
                fill="none"
                stroke="#6366f1"
                strokeWidth={2}
                strokeLinejoin="round"
              />

              {chartData.points.map((p, i) => (
                <circle
                  key={i}
                  cx={p.x}
                  cy={p.y}
                  r={hoveredIndex === i ? 6 : 3}
                  fill={hoveredIndex === i ? '#6366f1' : '#fff'}
                  stroke="#6366f1"
                  strokeWidth={2}
                  onMouseEnter={() => setHoveredIndex(i)}
                  style={{ cursor: 'pointer' }}
                />
              ))}
            </svg>

            {hovered && (
              <div
                style={{
                  position: 'absolute',
                  left: `${(hovered.x / CHART_WIDTH) * 100}%`,
                  top: `${(hovered.y / CHART_HEIGHT) * 100 - 12}%`,
                  transform: 'translate(-50%, -100%)',
                  background: '#1e1b4b',
                  color: '#fff',
                  padding: '6px 10px',
                  borderRadius: 6,
                  fontSize: 12,
                  whiteSpace: 'nowrap',
                  pointerEvents: 'none',
                  zIndex: 10,
                }}
              >
                <div>{formatMoney(hovered.snapshot.total_value)}</div>
                <div style={{ opacity: 0.75 }}>
                  {new Date(hovered.snapshot.recorded_at).toLocaleDateString('zh-CN')}
                </div>
              </div>
            )}
          </div>
        )}

        {!loading && !chartData && <p>暂无快照数据，点击"记录快照"开始追踪。</p>}
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>快照列表</h2>
            <p>共 {snapshots.length} 条记录</p>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>记录时间</th>
                <th>总资产</th>
              </tr>
            </thead>
            <tbody>
              {snapshots.map((s) => (
                <tr key={s.id}>
                  <td>{new Date(s.recorded_at).toLocaleString('zh-CN')}</td>
                  <td>{formatMoney(s.total_value)}</td>
                </tr>
              ))}
              {snapshots.length === 0 && (
                <tr>
                  <td colSpan={2}>暂无快照记录。</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}
