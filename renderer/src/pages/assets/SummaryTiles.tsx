import { FolderTree, Layers3, PieChart, WalletCards } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { Asset, PortfolioBucket } from '../../types'
import { formatPercent } from '../../utils/format'

interface SummaryTilesProps {
  structure: PortfolioBucket[]
  assets: Asset[]
}

export function SummaryTiles({ structure, assets }: SummaryTilesProps) {
  const targetTotal = structure.reduce((sum, bucket) => sum + bucket.target_weight, 0)
  const groupCount = structure.reduce((sum, bucket) => sum + bucket.groups.length, 0)
  const activeAssetCount = assets.filter((asset) => asset.is_active).length
  const pendingAssetCount = assets.filter((asset) => asset.is_active && !asset.include_in_portfolio).length

  return (
    <div className="config-summary-grid">
      <Tile
        icon={PieChart}
        label="目标配置合计"
        value={formatPercent(targetTotal)}
        tone={targetTotal === 1 ? 'good' : 'warn'}
      />
      <Tile icon={Layers3} label="资产大类" value={`${structure.length} 个`} />
      <Tile icon={FolderTree} label="资产细则" value={`${groupCount} 个`} />
      <Tile
        icon={WalletCards}
        label="启用标的"
        value={`${activeAssetCount} 个`}
        tone={pendingAssetCount === 0 ? 'good' : 'warn'}
      />
    </div>
  )
}

function Tile({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: LucideIcon
  label: string
  value: string
  tone?: 'good' | 'warn'
}) {
  return (
    <div className={`config-summary-tile ${tone ? `summary-${tone}` : ''}`}>
      <div className="config-summary-tile-icon">
        <Icon size={18} />
      </div>
      <div className="config-summary-tile-text">
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  )
}
