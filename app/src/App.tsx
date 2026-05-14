import { useEffect, useMemo, useState } from 'react'
import type { CSSProperties, FormEvent } from 'react'
import {
  Archive,
  ArrowLeft,
  ArrowDownUp,
  BarChart3,
  CalendarDays,
  ChartNoAxesCombined,
  ChartPie,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Eye,
  FileDown,
  Folder,
  Building2,
  CreditCard,
  DollarSign,
  Hash,
  Landmark,
  Link,
  ListChecks,
  LogOut,
  Plus,
  ReceiptText,
  RefreshCw,
  Scissors,
  Search,
  SlidersHorizontal,
  Tag,
  Trash2,
  Trophy,
  WalletCards,
} from 'lucide-react'
import { api } from './api/client'
import { useAuth } from './auth/useAuth'
import type {
  CashAccount,
  Instrument,
  InvestmentAccount,
  Portfolio,
  PortfolioSnapshot,
  TradingPlatform,
  Transaction,
  TransactionPayload,
} from './types'

const today = new Date().toISOString().slice(0, 10)

type Composer = 'transaction' | 'cash' | 'investment' | 'asset'
type ShortcutTarget = Composer | 'ledger' | 'distribution' | 'rebalance'
type AppScreen = 'home' | 'instrument-search' | 'transaction-create' | 'platform-select'
type TransactionDraft = {
  type: TransactionPayload['type']
  date: string
  qty: string
  price: string
  fee: string
  note: string
  accountId: string
  platformId: string
  cashAccountId: string
  linkCash: boolean
}

interface ShortcutItem {
  label: string
  target?: ShortcutTarget
  disabled?: boolean
  icon: typeof ReceiptText
}

const defaultTransactionDraft: TransactionDraft = {
  type: 'buy',
  date: today,
  qty: '',
  price: '',
  fee: '0',
  note: '',
  accountId: '',
  platformId: '',
  cashAccountId: '',
  linkCash: false,
}

function money(value: number) {
  return value.toLocaleString('zh-CN', { style: 'currency', currency: 'CNY' })
}

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

function signedMoney(value: number) {
  if (value === 0) return money(0)
  return `${value > 0 ? '+' : ''}${money(value)}`
}

function moneyTone(value: number) {
  if (value > 0) return 'positive'
  if (value < 0) return 'negative'
  return 'neutral'
}

function ratio(value: number) {
  return `${Math.max(0, Math.min(100, value * 100)).toFixed(2)}%`
}

function distributionGradient(segments: Array<{ value: number; color: string }>) {
  const activeSegments = segments.filter((segment) => segment.value > 0)
  const total = activeSegments.reduce((sum, segment) => sum + segment.value, 0)
  if (total <= 0) return '#dde5ee 0% 100%'

  let cursor = 0
  const slices = activeSegments.map((segment) => {
    const start = cursor
    cursor += (segment.value / total) * 100
    return `${segment.color} ${start.toFixed(2)}% ${cursor.toFixed(2)}%`
  })
  if (cursor < 100) slices.push(`#dde5ee ${cursor.toFixed(2)}% 100%`)
  return slices.join(', ')
}

function instrumentTypeLabel(type: Instrument['type']) {
  const labels: Record<Instrument['type'], string> = {
    stock: '股票',
    fund: '基金',
    etf: 'ETF',
    bond: '债券',
    gold: '黄金',
    crypto: '加密资产',
  }
  return labels[type]
}

function marketLabel(instrument: Instrument) {
  if (instrument.exchange === 'SH' || instrument.exchange === 'SZ') return '沪市股票'
  if (instrument.exchange === 'HK') return '港股'
  if (instrument.type === 'gold') return '黄金'
  return instrumentTypeLabel(instrument.type)
}

function instrumentCode(instrument: Instrument) {
  return [instrument.exchange, instrument.code].filter(Boolean).join('  ') || instrument.currency
}

function instrumentAccent(type: Instrument['type']) {
  if (type === 'stock') return 'red'
  if (type === 'gold') return 'gold'
  if (type === 'fund' || type === 'etf') return 'blue'
  return 'slate'
}

export default function App() {
  const { user, logout } = useAuth()
  const [portfolios, setPortfolios] = useState<Portfolio[]>([])
  const [portfolioId, setPortfolioId] = useState<number | null>(null)
  const [snapshot, setSnapshot] = useState<PortfolioSnapshot | null>(null)
  const [instruments, setInstruments] = useState<Instrument[]>([])
  const [investmentPlatforms, setInvestmentPlatforms] = useState<TradingPlatform[]>([])
  const [cashPlatforms, setCashPlatforms] = useState<TradingPlatform[]>([])
  const [investmentAccounts, setInvestmentAccounts] = useState<InvestmentAccount[]>([])
  const [cashAccounts, setCashAccounts] = useState<CashAccount[]>([])
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [activeComposer, setActiveComposer] = useState<Composer>('transaction')
  const [screen, setScreen] = useState<AppScreen>('home')
  const [instrumentQuery, setInstrumentQuery] = useState('')
  const [platformQuery, setPlatformQuery] = useState('')
  const [searchHistory, setSearchHistory] = useState<string[]>(['铂金9995', '贵州茅台', '黄金9999', '纳指ETF', '苹果'])
  const [selectedInstrument, setSelectedInstrument] = useState<Instrument | null>(null)
  const [transactionDraft, setTransactionDraft] = useState<TransactionDraft>(defaultTransactionDraft)
  const [instrumentLoading, setInstrumentLoading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const portfolio = useMemo(
    () => portfolios.find((item) => item.id === portfolioId) ?? null,
    [portfolioId, portfolios],
  )
  const stockGroups = useMemo(() => portfolio?.buckets.flatMap((bucket) => bucket.groups.map((group) => ({
    ...group,
    bucketName: bucket.name,
  }))) ?? [], [portfolio])

  const totalValue = snapshot?.total_value ?? 0
  const holdingsValue = snapshot?.holdings_value ?? 0
  const cashValue = snapshot?.cash_value ?? 0
  const holdingRows = [...(snapshot?.holdings ?? [])].sort((left, right) => right.market_value - left.market_value)
  const holdingPnl = holdingRows.reduce((sum, holding) => sum + holding.market_value - holding.cost_basis, 0)
  const investmentScore = holdingPnl
  const feeTotal = transactions.reduce((sum, tx) => sum + tx.fee, 0)
  const recentTransactions = transactions.slice(0, 8)
  const displayedInstruments = instruments.slice(0, 12)
  const selectedInvestmentAccount = investmentAccounts.find((account) => String(account.id) === transactionDraft.accountId) ?? null
  const selectedInvestmentPlatform = investmentPlatforms.find((platform) => String(platform.id) === transactionDraft.platformId) ?? null
  const selectedCashAccount = cashAccounts.find((account) => String(account.id) === transactionDraft.cashAccountId) ?? null
  const filteredInvestmentPlatforms = investmentPlatforms.filter((platform) => {
    const query = platformQuery.trim().toLowerCase()
    if (!query) return true
    return [platform.name, platform.type, platform.account_type]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query))
  })
  const transactionQty = Number(transactionDraft.qty || 0)
  const transactionPrice = Number(transactionDraft.price || 0)
  const transactionFee = Number(transactionDraft.fee || 0)
  const transactionAmount = transactionQty * transactionPrice + transactionFee
  const assetMix = [
    { label: '标的持仓', value: holdingsValue, color: '#2f7ff0' },
    { label: '现金仓位', value: cashValue, color: '#18a058' },
  ]
  const mixDonutStyle = {
    '--donut-gradient': distributionGradient(assetMix),
  } as CSSProperties

  const shortcuts: ShortcutItem[] = [
    { label: '交易记录', target: 'ledger', icon: ReceiptText },
    { label: '自定义', target: 'transaction', icon: Plus },
    { label: '变动趋势', disabled: true, icon: ChartNoAxesCombined },
    { label: '持仓分布', target: 'distribution', icon: ChartPie },
    { label: '再平衡', target: 'rebalance', icon: SlidersHorizontal },
    { label: '盈亏日历', disabled: true, icon: CalendarDays },
    { label: '模版导入', disabled: true, icon: FileDown },
    { label: '标签组', target: 'asset', icon: Tag },
    { label: '盈亏排行', disabled: true, icon: Trophy },
  ]

  async function loadInitial() {
    setLoading(true)
    setError(null)
    try {
      const [portfolioRows, instrumentRows, investmentPlatformRows, cashPlatformRows] = await Promise.all([
        api.listPortfolios(),
        api.listInstruments(undefined, 20),
        api.listTradingPlatforms('investment'),
        api.listTradingPlatforms('cash'),
      ])
      setPortfolios(portfolioRows)
      setInstruments(instrumentRows)
      setInvestmentPlatforms(investmentPlatformRows)
      setCashPlatforms(cashPlatformRows)
      setPortfolioId((current) => current ?? portfolioRows[0]?.id ?? null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  async function loadPortfolio(targetPortfolioId: number) {
    setError(null)
    try {
      const [snapshotRow, investmentAccountRows, cashAccountRows, transactionRows] = await Promise.all([
        api.getSnapshot(targetPortfolioId),
        api.listInvestmentAccounts(targetPortfolioId),
        api.listCashAccounts(targetPortfolioId),
        api.listTransactions(targetPortfolioId),
      ])
      setSnapshot(snapshotRow)
      setInvestmentAccounts(investmentAccountRows)
      setCashAccounts(cashAccountRows)
      setTransactions(transactionRows)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '加载失败')
    }
  }

  useEffect(() => {
    if (screen !== 'instrument-search') return undefined
    let cancelled = false
    const timer = window.setTimeout(() => {
      setInstrumentLoading(true)
      api.listInstruments(instrumentQuery.trim() || undefined, 20)
        .then((instrumentRows) => {
          if (!cancelled) setInstruments(instrumentRows)
        })
        .catch((caught) => {
          if (!cancelled) setError(caught instanceof Error ? caught.message : '加载标的失败')
        })
        .finally(() => {
          if (!cancelled) setInstrumentLoading(false)
        })
    }, instrumentQuery.trim() ? 260 : 0)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [instrumentQuery, screen])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadInitial()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [])

  useEffect(() => {
    if (portfolioId !== null) {
      const timer = window.setTimeout(() => {
        void loadPortfolio(portfolioId)
      }, 0)
      return () => window.clearTimeout(timer)
    }
    return undefined
  }, [portfolioId])

  async function refresh() {
    await loadInitial()
    if (portfolioId !== null) await loadPortfolio(portfolioId)
  }

  function scrollToSection(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  function openComposer(nextComposer: Composer) {
    if (nextComposer === 'transaction') {
      openInstrumentSearch()
      return
    }
    setActiveComposer(nextComposer)
    window.setTimeout(() => scrollToSection('quick-entry'), 0)
  }

  function updateTransactionDraft(next: Partial<TransactionDraft>) {
    setTransactionDraft((current) => ({ ...current, ...next }))
  }

  function openInstrumentSearch() {
    setError(null)
    setInstrumentQuery('')
    setScreen('instrument-search')
    window.scrollTo({ top: 0, behavior: 'auto' })
  }

  function openTransactionCreate(instrument: Instrument) {
    const keyword = instrument.name
    const defaultAccount = investmentAccounts[0] ?? null
    setSelectedInstrument(instrument)
    setSearchHistory((current) => [keyword, ...current.filter((item) => item !== keyword)].slice(0, 8))
    setTransactionDraft({
      ...defaultTransactionDraft,
      price: instrument.latest_price === null ? '' : String(instrument.latest_price),
      accountId: defaultAccount ? String(defaultAccount.id) : '',
      platformId: defaultAccount?.trading_platform_id ? String(defaultAccount.trading_platform_id) : '',
      cashAccountId: cashAccounts[0]?.id ? String(cashAccounts[0].id) : '',
      linkCash: cashAccounts.length > 0,
    })
    setError(null)
    setScreen('transaction-create')
    window.scrollTo({ top: 0, behavior: 'auto' })
  }

  function backToHome() {
    setScreen('home')
    setError(null)
    window.scrollTo({ top: 0, behavior: 'auto' })
  }

  function backToInstrumentSearch() {
    setScreen('instrument-search')
    setError(null)
    window.scrollTo({ top: 0, behavior: 'auto' })
  }

  function openPlatformSelect() {
    setPlatformQuery('')
    setError(null)
    setScreen('platform-select')
    window.scrollTo({ top: 0, behavior: 'auto' })
  }

  function chooseTradingPlatform(platform: TradingPlatform) {
    const existingAccount = investmentAccounts.find((account) => account.trading_platform_id === platform.id) ?? null
    updateTransactionDraft({
      platformId: String(platform.id),
      accountId: existingAccount ? String(existingAccount.id) : '',
    })
    setScreen('transaction-create')
    setError(null)
    window.scrollTo({ top: 0, behavior: 'auto' })
  }

  function handleShortcut(item: ShortcutItem) {
    if (item.disabled || !item.target) return
    if (item.target === 'ledger') {
      scrollToSection('ledger')
      return
    }
    if (item.target === 'distribution') {
      scrollToSection('distribution')
      return
    }
    if (item.target === 'rebalance') {
      scrollToSection('rebalance')
      return
    }
    openComposer(item.target)
  }

  async function submitInvestmentAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!portfolioId) return
    const form = event.currentTarget
    const data = new FormData(form)
    await api.createInvestmentAccount({
      portfolio_id: portfolioId,
      trading_platform_id: Number(data.get('platform')),
      name: String(data.get('name') || ''),
      is_active: true,
    })
    form.reset()
    await loadPortfolio(portfolioId)
  }

  async function submitCashAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!portfolioId) return
    const form = event.currentTarget
    const data = new FormData(form)
    await api.createCashAccount({
      portfolio_id: portfolioId,
      trading_platform_id: data.get('platform') ? Number(data.get('platform')) : null,
      name: String(data.get('name') || ''),
      currency: 'CNY',
      balance: Number(data.get('balance') || 0),
      balance_date: today,
      include_in_rebalance: data.get('include_in_rebalance') === 'on',
      is_active: true,
    })
    form.reset()
    await loadPortfolio(portfolioId)
  }

  async function submitUserAsset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!portfolioId) return
    const form = event.currentTarget
    const data = new FormData(form)
    await api.createUserAsset({
      portfolio_id: portfolioId,
      instrument_id: Number(data.get('instrument')),
      portfolio_group_id: data.get('group') ? Number(data.get('group')) : null,
      account_id: data.get('account') ? Number(data.get('account')) : null,
      display_name: null,
      target_weight: Number(data.get('target_weight') || 0),
      include_in_rebalance: true,
      is_active: true,
    })
    form.reset()
    await loadPortfolio(portfolioId)
  }

  async function submitTransaction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!portfolioId || !selectedInstrument) return
    let accountId = transactionDraft.accountId ? Number(transactionDraft.accountId) : null
    if (!accountId && transactionDraft.platformId) {
      const platformId = Number(transactionDraft.platformId)
      const platform = investmentPlatforms.find((item) => item.id === platformId)
      const createdAccount = await api.createInvestmentAccount({
        portfolio_id: portfolioId,
        trading_platform_id: platformId,
        name: platform?.name ?? '投资账户',
        is_active: true,
      })
      accountId = createdAccount.id
      setInvestmentAccounts((current) => [...current, createdAccount])
    }
    const payload: TransactionPayload = {
      portfolio_id: portfolioId,
      instrument_id: selectedInstrument.id,
      account_id: accountId,
      cash_account_id: transactionDraft.linkCash && transactionDraft.cashAccountId ? Number(transactionDraft.cashAccountId) : null,
      date: transactionDraft.date || today,
      type: transactionDraft.type,
      qty: Number(transactionDraft.qty || 0),
      price: Number(transactionDraft.price || 0),
      fee: Number(transactionDraft.fee || 0),
      note: transactionDraft.note || null,
    }
    await api.createTransaction(payload)
    setSelectedInstrument(null)
    setTransactionDraft(defaultTransactionDraft)
    setScreen('home')
    await loadPortfolio(portfolioId)
  }

  if (screen === 'instrument-search') {
    return (
      <main className="subpage-shell">
        <div className="subpage-content">
          <header className="instrument-search-head">
            <label className="instrument-search-box">
              <Search size={24} />
              <input
                value={instrumentQuery}
                onChange={(event) => setInstrumentQuery(event.target.value)}
                placeholder="股票基金名称/代码/首字母"
                aria-label="搜索标的"
                autoFocus
              />
            </label>
            <button type="button" onClick={backToHome}>取消</button>
          </header>

          <section className="search-history-block">
            <div className="subsection-title-row">
              <h1>搜索历史</h1>
              <button type="button" onClick={() => setSearchHistory([])} aria-label="清空搜索历史">
                <Trash2 size={22} />
              </button>
            </div>
            <div className="history-chip-list">
              {searchHistory.length > 0 ? searchHistory.map((keyword) => (
                <button key={keyword} type="button" onClick={() => setInstrumentQuery(keyword)}>
                  {keyword}
                </button>
              )) : <span>暂无搜索历史</span>}
            </div>
          </section>

          <section className="instrument-list-section">
            <h2>{instrumentQuery.trim() ? '搜索结果' : '热门资产'}</h2>
            <div className="instrument-result-list">
              {instrumentLoading ? <div className="empty-state">加载标的中...</div> : null}
              {!instrumentLoading && displayedInstruments.map((instrument) => (
                <button key={instrument.id} className="instrument-row" type="button" onClick={() => openTransactionCreate(instrument)}>
                  <div className="instrument-row-main">
                    <strong>{instrument.name}</strong>
                    <span>
                      <em className={`market-badge ${instrumentAccent(instrument.type)}`}>{instrument.exchange || instrument.currency}</em>
                      {instrument.code || instrument.currency}
                    </span>
                  </div>
                  <span className={`instrument-kind ${instrumentAccent(instrument.type)}`}>{marketLabel(instrument)}</span>
                  <ChevronRight size={24} />
                </button>
              ))}
              {!instrumentLoading && displayedInstruments.length === 0 ? (
                <div className="empty-state">暂无匹配标的</div>
              ) : null}
            </div>
          </section>
        </div>
      </main>
    )
  }

  if (screen === 'transaction-create' && selectedInstrument) {
    return (
      <main className="subpage-shell transaction-page">
        <div className="subpage-content">
          <header className="subpage-nav">
            <button type="button" onClick={backToInstrumentSearch} aria-label="返回选择标的">
              <ArrowLeft size={28} />
            </button>
            <h1>新增交易</h1>
            <button form="transaction-create-form" type="submit">保存</button>
          </header>

          {error ? <div className="alert">{error}</div> : null}

          <form id="transaction-create-form" className="transaction-create-form" onSubmit={(event) => void submitTransaction(event)}>
            <section className="entry-card">
              <button className="entry-row" type="button" onClick={backToInstrumentSearch}>
                <ChartPie size={24} />
                <span>{instrumentTypeLabel(selectedInstrument.type)}: {selectedInstrument.name} / {instrumentCode(selectedInstrument)}</span>
                <ChevronRight size={22} />
              </button>

              <button className="entry-row" type="button" onClick={openPlatformSelect}>
                <Building2 size={24} />
                <span>交易平台: {selectedInvestmentPlatform?.name ?? selectedInvestmentAccount?.platform_name ?? '未选择'}</span>
                {selectedInvestmentAccount?.name ? <strong>{selectedInvestmentAccount.name}</strong> : null}
                <ChevronRight size={22} />
              </button>

              <div className="entry-row">
                <Archive size={24} />
                <span>投资组合: {portfolio?.name ?? '默认组合'}</span>
              </div>

              <div className="entry-row type-row">
                <ArrowDownUp size={24} />
                <span>类型</span>
                <div className="type-segment">
                  <button
                    type="button"
                    className={transactionDraft.type === 'buy' ? 'active' : ''}
                    onClick={() => updateTransactionDraft({ type: 'buy' })}
                  >
                    买入
                  </button>
                  <button
                    type="button"
                    className={transactionDraft.type === 'sell' ? 'active' : ''}
                    onClick={() => updateTransactionDraft({ type: 'sell' })}
                  >
                    卖出
                  </button>
                </div>
              </div>
            </section>

            <section className="entry-card">
              <label className="entry-row">
                <CalendarDays size={24} />
                <span>交易日期:</span>
                <input
                  type="date"
                  value={transactionDraft.date}
                  onChange={(event) => updateTransactionDraft({ date: event.target.value })}
                  aria-label="交易日期"
                />
                <ChevronRight size={22} />
              </label>
            </section>

            <section className="entry-card">
              <label className="entry-row">
                <Hash size={24} />
                <span>数量:</span>
                <input
                  required
                  inputMode="decimal"
                  type="number"
                  step="0.0001"
                  min="0"
                  value={transactionDraft.qty}
                  onChange={(event) => updateTransactionDraft({ qty: event.target.value })}
                  placeholder="0.00"
                  aria-label="数量"
                />
                <ChevronRight size={22} />
              </label>

              <label className="entry-row">
                <DollarSign size={24} />
                <span>价格:</span>
                <input
                  required
                  inputMode="decimal"
                  type="number"
                  step="0.0001"
                  min="0"
                  value={transactionDraft.price}
                  onChange={(event) => updateTransactionDraft({ price: event.target.value })}
                  placeholder="0.00"
                  aria-label="价格"
                />
                <ChevronRight size={22} />
              </label>

              <label className="entry-row">
                <Scissors size={24} />
                <span>佣金:</span>
                <input
                  inputMode="decimal"
                  type="number"
                  step="0.01"
                  min="0"
                  value={transactionDraft.fee}
                  onChange={(event) => updateTransactionDraft({ fee: event.target.value })}
                  placeholder="0.00"
                  aria-label="佣金"
                />
                <ChevronRight size={22} />
              </label>

              <div className="entry-row amount-row">
                <CreditCard size={24} />
                <span>{transactionDraft.type === 'buy' ? '买入金额' : '卖出金额'}: {money(transactionAmount)}</span>
              </div>
            </section>

            <section className="entry-card">
              <label className="entry-row cash-toggle-row">
                <Link size={24} />
                <span>关联现金账户</span>
                <input
                  type="checkbox"
                  checked={transactionDraft.linkCash}
                  onChange={(event) => updateTransactionDraft({ linkCash: event.target.checked })}
                  aria-label="关联现金账户"
                />
              </label>
              {transactionDraft.linkCash ? (
                <label className="entry-row">
                  <WalletCards size={24} />
                  <span>现金账户:</span>
                  <select
                    value={transactionDraft.cashAccountId}
                    onChange={(event) => updateTransactionDraft({ cashAccountId: event.target.value })}
                    aria-label="现金账户"
                  >
                    <option value="">未选择</option>
                    {cashAccounts.map((account) => (
                      <option key={account.id} value={account.id}>{account.name}</option>
                    ))}
                  </select>
                  <ChevronRight size={22} />
                </label>
              ) : null}
            </section>

            <section className="entry-card">
              <label className="entry-row note-row">
                <Tag size={24} />
                <span>备注:</span>
                <input
                  value={transactionDraft.note}
                  onChange={(event) => updateTransactionDraft({ note: event.target.value })}
                  aria-label="备注"
                />
              </label>
            </section>

            <div className="transaction-context">
              <span>交易平台: {selectedInvestmentPlatform?.name ?? selectedInvestmentAccount?.platform_name ?? '未选择'}</span>
              <span>现金账户: {transactionDraft.linkCash ? selectedCashAccount?.name ?? '未选择' : '未关联'}</span>
            </div>
          </form>
        </div>
      </main>
    )
  }

  if (screen === 'platform-select') {
    return (
      <main className="subpage-shell">
        <div className="subpage-content">
          <header className="subpage-nav">
            <button type="button" onClick={() => setScreen('transaction-create')} aria-label="返回新增交易">
              <ArrowLeft size={28} />
            </button>
            <h1>请选择交易平台</h1>
            <button type="button">佣金费率设置</button>
          </header>

          <label className="instrument-search-box platform-search-box">
            <Search size={24} />
            <input
              value={platformQuery}
              onChange={(event) => setPlatformQuery(event.target.value)}
              placeholder="搜索交易平台"
              aria-label="搜索交易平台"
              autoFocus
            />
          </label>

          <section className="platform-list-section">
            <div className="platform-group-title">
              <span>★</span>
            </div>
            <div className="platform-result-list">
              {filteredInvestmentPlatforms.map((platform) => (
                <button key={platform.id} className="platform-row" type="button" onClick={() => chooseTradingPlatform(platform)}>
                  <div className="platform-logo">
                    {platform.name.slice(0, 1)}
                  </div>
                  <div className="platform-row-main">
                    <strong>{platform.name}</strong>
                    <span>{platform.account_type || platform.type}</span>
                  </div>
                  <ChevronRight size={24} />
                </button>
              ))}
              {filteredInvestmentPlatforms.length === 0 ? (
                <div className="empty-state platform-empty-state">
                  <Building2 size={28} />
                  <span>暂无交易平台</span>
                  <small>请先在运营后台维护交易平台，或确认本地默认平台已初始化。</small>
                </div>
              ) : null}
            </div>
          </section>

          <div className="letter-index" aria-hidden="true">
            <span>★</span>
            <span>🔥</span>
            <span>A</span>
            <span>B</span>
            <span>C</span>
            <span>D</span>
            <span>E</span>
            <span>F</span>
            <span>G</span>
            <span>H</span>
            <span>I</span>
            <span>J</span>
            <span>K</span>
            <span>L</span>
            <span>M</span>
            <span>N</span>
            <span>O</span>
            <span>P</span>
            <span>Q</span>
            <span>R</span>
            <span>S</span>
            <span>T</span>
            <span>W</span>
            <span>X</span>
            <span>Y</span>
            <span>Z</span>
          </div>
        </div>
      </main>
    )
  }

  return (
    <main className="app-home">
      <div className="mobile-shell">
        <header className="mobile-topbar">
          <button className="ghost-icon-button" type="button" aria-label="组合目录">
            <Folder size={28} />
          </button>
          <button className="guide-button" type="button" aria-label="新手指南">
            <CircleHelp size={22} />
            <span>新手指南</span>
          </button>
        </header>

        <section className="portfolio-head">
          <div className="portfolio-copy">
            <div className="portfolio-select-wrap">
              <select
                className="portfolio-select"
                aria-label="选择组合"
                value={portfolioId ?? ''}
                onChange={(event) => setPortfolioId(Number(event.target.value))}
              >
                {portfolios.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
              <ChevronDown size={22} aria-hidden="true" />
            </div>
            <p>{portfolio?.strategy_type === 'permanent_portfolio' ? '永久组合' : portfolio?.base_currency ?? 'CNY'}</p>
          </div>
          <div className="avatar-button" aria-label="当前用户">
            {(user?.name || user?.email || 'B').slice(0, 1).toUpperCase()}
          </div>
        </section>

        {error ? <div className="alert">{error}</div> : null}
        {loading ? <div className="soft-card loading-panel">加载中...</div> : null}

        <section className="summary-card">
          <div className="summary-top">
            <div>
              <span className="summary-label">持仓总资产</span>
              <span className="summary-icons">
                <CircleHelp size={14} />
                <Eye size={17} />
              </span>
              <strong className="summary-total">{money(totalValue)}</strong>
            </div>
            <div className="score-block">
              <span>投资成绩 <ChevronRight size={14} /></span>
              <strong className={moneyTone(investmentScore)}>{signedMoney(investmentScore)}</strong>
            </div>
          </div>
          <div className="summary-grid">
            <div>
              <span>已实现盈亏 <ChevronRight size={13} /></span>
              <strong>{money(0)}</strong>
            </div>
            <div>
              <span>持仓盈亏 <CircleHelp size={13} /></span>
              <strong className={moneyTone(holdingPnl)}>{signedMoney(holdingPnl)}</strong>
            </div>
            <div>
              <span>现金 <ChevronRight size={13} /></span>
              <strong>{money(cashValue)}</strong>
            </div>
            <div>
              <span>手续费 <ChevronRight size={13} /></span>
              <strong>{money(feeTotal)}</strong>
            </div>
            <div>
              <span>分红 <ChevronRight size={13} /></span>
              <strong>{money(0)}</strong>
            </div>
          </div>
        </section>

        <nav className="shortcut-grid" aria-label="首页快捷入口">
          {shortcuts.map((item) => {
            const Icon = item.icon
            return (
              <button
                key={item.label}
                className={item.disabled ? 'disabled' : ''}
                type="button"
                disabled={item.disabled}
                onClick={() => handleShortcut(item)}
              >
                <Icon size={25} />
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>

        <section id="holdings" className="holdings-section">
          <div className="section-title-row">
            <h2>我的持仓 ({holdingRows.length})</h2>
            <div className="holding-actions">
              <button type="button" onClick={() => void refresh()}>
                <RefreshCw size={16} />
                同步价格
              </button>
              <ArrowDownUp size={22} aria-hidden="true" />
            </div>
          </div>

          <div className="holding-list-card">
            {holdingRows.length > 0 ? holdingRows.map((holding) => {
              const pnl = holding.market_value - holding.cost_basis
              return (
                <article key={holding.user_asset_id} className="holding-item">
                  <div className="holding-item-head">
                    <div className="holding-logo">{holding.name.slice(0, 1)}</div>
                    <div className="holding-name">
                      <strong>{holding.name}</strong>
                      <small>{holding.group_name || holding.bucket_name || '未分类'}</small>
                    </div>
                    <div className="holding-money">
                      <strong className={moneyTone(pnl)}>{signedMoney(pnl)}</strong>
                      <ChevronDown size={16} />
                    </div>
                  </div>
                  <div className="holding-table">
                    <span>名称/代码</span>
                    <span>市值/份额</span>
                    <span>现价/成本</span>
                    <span>持仓盈亏</span>
                    <strong>{holding.name}</strong>
                    <strong>{money(holding.market_value)}</strong>
                    <strong>{holding.latest_price === null ? '-' : holding.latest_price.toFixed(4)}</strong>
                    <strong className={moneyTone(pnl)}>{signedMoney(pnl)}</strong>
                    <small>{holding.instrument_code || holding.instrument_exchange || holding.instrument_id}</small>
                    <small>{holding.quantity}</small>
                    <small>{holding.average_cost.toFixed(4)}</small>
                    <small>{holding.cost_basis ? percent(pnl / holding.cost_basis) : '0.0%'}</small>
                  </div>
                </article>
              )
            }) : (
              <div className="empty-holding">
                <WalletCards size={28} />
                <span>暂无持仓</span>
              </div>
            )}
          </div>
        </section>

        <section id="distribution" className="soft-card compact-panel">
          <div className="panel-title-row">
            <h2>持仓分布</h2>
            <ChartPie size={20} />
          </div>
          <div className="distribution-body">
            <div className="donut" style={mixDonutStyle} aria-label="资产分布">
              <span>{totalValue > 0 ? percent(holdingsValue / totalValue) : '0.0%'}</span>
              <small>持仓</small>
            </div>
            <div className="legend-list">
              {assetMix.map((segment) => (
                <div key={segment.label} className="legend-row">
                  <span className="legend-dot" style={{ '--dot-color': segment.color } as CSSProperties} />
                  <span>{segment.label}</span>
                  <strong>{money(segment.value)}</strong>
                  <small>{totalValue > 0 ? percent(segment.value / totalValue) : '0.0%'}</small>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="rebalance" className="soft-card compact-panel">
          <div className="panel-title-row">
            <h2>再平衡</h2>
            <SlidersHorizontal size={20} />
          </div>
          <div className="bucket-list">
            {(snapshot?.buckets ?? []).map((bucket) => (
              <div key={bucket.name} className="bucket-row">
                <div className="bucket-row-main">
                  <span>{bucket.name}</span>
                  <strong>{money(bucket.current_value)}</strong>
                </div>
                <div className="bucket-meter">
                  <span className="bucket-meter-fill" style={{ '--bar-width': ratio(bucket.actual_weight) } as CSSProperties} />
                  <span className="bucket-meter-target" style={{ '--target-left': ratio(bucket.target_weight) } as CSSProperties} />
                </div>
                <div className="bucket-row-meta">
                  <small>当前 {percent(bucket.actual_weight)}</small>
                  <small>目标 {percent(bucket.target_weight)}</small>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section id="accounts" className="soft-card compact-panel">
          <div className="panel-title-row">
            <h2>资产账户</h2>
            <Landmark size={20} />
          </div>
          <div className="account-list">
            {cashAccounts.map((account) => (
              <div key={account.id} className="account-row">
                <span>{account.name}</span>
                <strong>{money(account.balance)}</strong>
                <small>{account.platform_name || '未绑定平台'}</small>
              </div>
            ))}
            {investmentAccounts.map((account) => (
              <div key={account.id} className="account-row">
                <span>{account.name}</span>
                <strong>{account.platform_name || '未绑定平台'}</strong>
                <small>{account.platform_type || 'investment'}</small>
              </div>
            ))}
            {cashAccounts.length + investmentAccounts.length === 0 ? <div className="empty-state">暂无账户</div> : null}
          </div>
        </section>

        <section id="quick-entry" className="soft-card compact-panel">
          <div className="panel-title-row">
            <h2>快速录入</h2>
            <ReceiptText size={20} />
          </div>

          <div className="composer-tabs" role="tablist" aria-label="录入类型">
            <button
              type="button"
              className={activeComposer === 'transaction' ? 'active' : ''}
              onClick={() => setActiveComposer('transaction')}
            >
              交易
            </button>
            <button
              type="button"
              className={activeComposer === 'asset' ? 'active' : ''}
              onClick={() => setActiveComposer('asset')}
            >
              标的
            </button>
            <button
              type="button"
              className={activeComposer === 'cash' ? 'active' : ''}
              onClick={() => setActiveComposer('cash')}
            >
              现金
            </button>
            <button
              type="button"
              className={activeComposer === 'investment' ? 'active' : ''}
              onClick={() => setActiveComposer('investment')}
            >
              账户
            </button>
          </div>

          {activeComposer === 'transaction' ? (
            <button className="entry-launcher" type="button" onClick={openInstrumentSearch}>
              <Search size={20} />
              先选择标的，再新增交易
              <ChevronRight size={20} />
            </button>
          ) : null}

          {activeComposer === 'asset' ? (
            <form className="inline-form asset-form" onSubmit={(event) => void submitUserAsset(event)}>
              <select name="instrument" required defaultValue="" aria-label="配置标的">
                <option value="" disabled>标的</option>
                {instruments.map((instrument) => (
                  <option key={instrument.id} value={instrument.id}>{instrument.name}</option>
                ))}
              </select>
              <select name="group" defaultValue="" aria-label="细分类">
                <option value="">细分类</option>
                {stockGroups.map((group) => (
                  <option key={group.id} value={group.id}>{group.bucketName} / {group.name}</option>
                ))}
              </select>
              <select name="account" defaultValue="" aria-label="投资账户">
                <option value="">账户</option>
                {investmentAccounts.map((account) => (
                  <option key={account.id} value={account.id}>{account.name}</option>
                ))}
              </select>
              <input name="target_weight" type="number" min="0" max="1" step="0.01" placeholder="目标权重" aria-label="目标权重" />
              <button type="submit"><Plus size={16} />添加</button>
            </form>
          ) : null}

          {activeComposer === 'cash' ? (
            <form className="inline-form cash-form" onSubmit={(event) => void submitCashAccount(event)}>
              <input name="name" required placeholder="账户名称" aria-label="现金账户名称" />
              <select name="platform" defaultValue="" aria-label="现金平台">
                <option value="">平台</option>
                {cashPlatforms.map((platform) => (
                  <option key={platform.id} value={platform.id}>{platform.name}</option>
                ))}
              </select>
              <input name="balance" required type="number" step="0.01" placeholder="余额" aria-label="现金余额" />
              <label className="checkline">
                <input name="include_in_rebalance" type="checkbox" defaultChecked />
                参与再平衡
              </label>
              <button type="submit"><Plus size={16} />新增</button>
            </form>
          ) : null}

          {activeComposer === 'investment' ? (
            <form className="inline-form investment-form" onSubmit={(event) => void submitInvestmentAccount(event)}>
              <input name="name" required placeholder="账户名称" aria-label="投资账户名称" />
              <select name="platform" required defaultValue="" aria-label="交易平台">
                <option value="" disabled>交易平台</option>
                {investmentPlatforms.map((platform) => (
                  <option key={platform.id} value={platform.id}>{platform.name}</option>
                ))}
              </select>
              <button type="submit"><Plus size={16} />新增</button>
            </form>
          ) : null}
        </section>

        <section id="ledger" className="soft-card compact-panel ledger-panel">
          <div className="panel-title-row">
            <h2>交易记录</h2>
            <ListChecks size={20} />
          </div>
          <div className="transaction-list">
            {recentTransactions.length > 0 ? recentTransactions.map((tx) => (
              <div key={tx.id} className="transaction-row">
                <div>
                  <span>{tx.instrument_name}</span>
                  <small>{tx.account_name || '未绑定投资账户'} · {tx.cash_account_name || '未联动现金'}</small>
                </div>
                <strong>{tx.type === 'buy' ? '买入' : '卖出'} {money(tx.amount)}</strong>
              </div>
            )) : (
              <div className="empty-state">暂无交易流水</div>
            )}
          </div>
        </section>
      </div>

      <button className="floating-add" type="button" onClick={openInstrumentSearch} aria-label="新增交易">
        <Plus size={34} />
      </button>

      <nav className="bottom-nav" aria-label="主导航">
        <button className="active" type="button" onClick={() => scrollToSection('holdings')}>
          <ChartPie size={22} />
          <span>持仓</span>
        </button>
        <button type="button" onClick={() => scrollToSection('accounts')}>
          <WalletCards size={22} />
          <span>资产</span>
        </button>
        <button className="disabled" type="button" disabled>
          <BarChart3 size={22} />
          <span>支出</span>
        </button>
        <button type="button" onClick={logout}>
          <LogOut size={22} />
          <span>退出</span>
        </button>
      </nav>
    </main>
  )
}
