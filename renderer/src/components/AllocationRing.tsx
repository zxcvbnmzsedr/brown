import type { SnapshotBucket } from '../types'
import { formatMoney, formatPercent } from '../utils/format'

const COLORS = ['#5b8def', '#49b881', '#f4b860', '#f06f6f', '#8f7ee7', '#52b8c8']

function buildGradient(buckets: SnapshotBucket[], key: 'actual_weight' | 'target_weight'): string {
  const weightedBuckets = buckets.filter((bucket) => bucket[key] > 0)
  const total = weightedBuckets.reduce((sum, bucket) => sum + bucket[key], 0)

  if (total <= 0) {
    return '#e7ecf3 0deg 360deg'
  }

  let cursor = 0
  return weightedBuckets
    .map((bucket, index) => {
      const start = cursor
      const size = (bucket[key] / total) * 360
      cursor += size
      return `${COLORS[index % COLORS.length]} ${start}deg ${cursor}deg`
    })
    .join(', ')
}

interface AllocationRingProps {
  buckets: SnapshotBucket[]
  totalValue: number
}

export function AllocationRing({ buckets, totalValue }: AllocationRingProps) {
  return (
    <div className="allocation-visual" aria-label="组合配置图">
      <div
        className="allocation-ring allocation-ring-actual"
        style={{ background: `conic-gradient(${buildGradient(buckets, 'actual_weight')})` }}
      >
        <div
          className="allocation-ring allocation-ring-target"
          style={{ background: `conic-gradient(${buildGradient(buckets, 'target_weight')})` }}
        >
          <div className="allocation-center">
            <span>总资产</span>
            <strong>{formatMoney(totalValue)}</strong>
          </div>
        </div>
      </div>
      <div className="allocation-legend">
        {buckets.map((bucket, index) => (
          <div className="legend-row" key={bucket.bucket_id}>
            <span className="legend-dot" style={{ background: COLORS[index % COLORS.length] }} />
            <span>{bucket.name}</span>
            <strong>{formatPercent(bucket.actual_weight)}</strong>
          </div>
        ))}
      </div>
    </div>
  )
}
