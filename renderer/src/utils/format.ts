export function formatMoney(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '-'
  }

  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
    maximumFractionDigits: 2,
  }).format(value)
}

export function formatNumber(value: number | null | undefined, digits = 4): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '-'
  }

  return new Intl.NumberFormat('zh-CN', {
    maximumFractionDigits: digits,
  }).format(value)
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '-'
  }

  return new Intl.NumberFormat('zh-CN', {
    style: 'percent',
    maximumFractionDigits: digits,
  }).format(value)
}

export function today(): string {
  const d = new Date()
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return '-'
  }

  return new Date(value).toLocaleString('zh-CN')
}
