import type { LucideIcon } from 'lucide-react'

interface MetricCardProps {
  icon: LucideIcon
  label: string
  value: string
  tone?: 'neutral' | 'good' | 'warn'
}

export function MetricCard({ icon: Icon, label, value, tone = 'neutral' }: MetricCardProps) {
  return (
    <section className={`metric-card metric-card-${tone}`}>
      <div className="metric-icon">
        <Icon size={18} aria-hidden="true" />
      </div>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
      </div>
    </section>
  )
}
