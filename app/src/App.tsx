import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import {
  ArrowDownCircle,
  ArrowUpCircle,
  Landmark,
  LogOut,
  PiggyBank,
  Plus,
  RefreshCw,
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
  UserAsset,
} from './types'

const today = new Date().toISOString().slice(0, 10)

function money(value: number) {
  return value.toLocaleString('zh-CN', { style: 'currency', currency: 'CNY' })
}

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`
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
  const [userAssets, setUserAssets] = useState<UserAsset[]>([])
  const [transactions, setTransactions] = useState<Transaction[]>([])
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

  async function loadInitial() {
    setLoading(true)
    setError(null)
    try {
      const [portfolioRows, instrumentRows, investmentPlatformRows, cashPlatformRows] = await Promise.all([
        api.listPortfolios(),
        api.listInstruments(),
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
      const [snapshotRow, investmentAccountRows, cashAccountRows, assetRows, transactionRows] = await Promise.all([
        api.getSnapshot(targetPortfolioId),
        api.listInvestmentAccounts(targetPortfolioId),
        api.listCashAccounts(targetPortfolioId),
        api.listUserAssets(targetPortfolioId),
        api.listTransactions(targetPortfolioId),
      ])
      setSnapshot(snapshotRow)
      setInvestmentAccounts(investmentAccountRows)
      setCashAccounts(cashAccountRows)
      setUserAssets(assetRows)
      setTransactions(transactionRows)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '加载失败')
    }
  }

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
    if (!portfolioId) return
    const form = event.currentTarget
    const data = new FormData(form)
    const payload: TransactionPayload = {
      portfolio_id: portfolioId,
      instrument_id: Number(data.get('instrument')),
      account_id: data.get('account') ? Number(data.get('account')) : null,
      cash_account_id: data.get('cash_account') ? Number(data.get('cash_account')) : null,
      date: String(data.get('date') || today),
      type: data.get('type') as TransactionPayload['type'],
      qty: Number(data.get('qty') || 0),
      price: Number(data.get('price') || 0),
      fee: Number(data.get('fee') || 0),
      note: String(data.get('note') || '') || null,
    }
    await api.createTransaction(payload)
    form.reset()
    await loadPortfolio(portfolioId)
  }

  return (
    <main className="workspace">
      <header className="topbar">
        <div>
          <h1>Brown</h1>
          <p>资产统计、现金账户与永久组合再平衡</p>
        </div>
        <div className="topbar-actions">
          <select value={portfolioId ?? ''} onChange={(event) => setPortfolioId(Number(event.target.value))}>
            {portfolios.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>
          <button className="icon-button" type="button" onClick={() => void refresh()} aria-label="刷新">
            <RefreshCw size={18} />
          </button>
          <span>{user?.name || user?.email}</span>
          <button className="icon-button" type="button" onClick={logout} aria-label="退出">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      {error ? <div className="alert">{error}</div> : null}
      {loading ? <div className="panel">加载中...</div> : null}

      <section className="metrics">
        <article>
          <WalletCards size={20} />
          <span>总资产</span>
          <strong>{money(snapshot?.total_value ?? 0)}</strong>
        </article>
        <article>
          <Landmark size={20} />
          <span>标的持仓</span>
          <strong>{money(snapshot?.holdings_value ?? 0)}</strong>
        </article>
        <article>
          <PiggyBank size={20} />
          <span>现金仓位</span>
          <strong>{money(snapshot?.cash_value ?? 0)}</strong>
        </article>
      </section>

      <section className="grid two">
        <div className="panel">
          <h2>资产桶</h2>
          <div className="bucket-list">
            {snapshot?.buckets.map((bucket) => (
              <div key={bucket.name} className="bucket-row">
                <span>{bucket.name}</span>
                <strong>{money(bucket.current_value)}</strong>
                <small>{percent(bucket.actual_weight)} / 目标 {percent(bucket.target_weight)}</small>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <h2>现金账户</h2>
          <form className="inline-form" onSubmit={(event) => void submitCashAccount(event)}>
            <input name="name" required placeholder="账户名称" />
            <select name="platform" defaultValue="">
              <option value="">平台</option>
              {cashPlatforms.map((platform) => (
                <option key={platform.id} value={platform.id}>{platform.name}</option>
              ))}
            </select>
            <input name="balance" required type="number" step="0.01" placeholder="余额" />
            <label className="checkline">
              <input name="include_in_rebalance" type="checkbox" defaultChecked />
              参与再平衡
            </label>
            <button type="submit"><Plus size={16} />新增</button>
          </form>
          <div className="table-list">
            {cashAccounts.map((account) => (
              <div key={account.id} className="table-row">
                <span>{account.name}</span>
                <strong>{money(account.balance)}</strong>
                <small>{account.platform_name || '未绑定平台'}</small>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid two">
        <div className="panel">
          <h2>投资账户</h2>
          <form className="inline-form" onSubmit={(event) => void submitInvestmentAccount(event)}>
            <input name="name" required placeholder="账户名称" />
            <select name="platform" required defaultValue="">
              <option value="" disabled>交易平台</option>
              {investmentPlatforms.map((platform) => (
                <option key={platform.id} value={platform.id}>{platform.name}</option>
              ))}
            </select>
            <button type="submit"><Plus size={16} />新增</button>
          </form>
          <div className="table-list">
            {investmentAccounts.map((account) => (
              <div key={account.id} className="table-row">
                <span>{account.name}</span>
                <small>{account.platform_name}</small>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <h2>配置标的</h2>
          <form className="inline-form" onSubmit={(event) => void submitUserAsset(event)}>
            <select name="instrument" required defaultValue="">
              <option value="" disabled>标的</option>
              {instruments.map((instrument) => (
                <option key={instrument.id} value={instrument.id}>{instrument.name}</option>
              ))}
            </select>
            <select name="group" defaultValue="">
              <option value="">细分类</option>
              {stockGroups.map((group) => (
                <option key={group.id} value={group.id}>{group.bucketName} / {group.name}</option>
              ))}
            </select>
            <select name="account" defaultValue="">
              <option value="">账户</option>
              {investmentAccounts.map((account) => (
                <option key={account.id} value={account.id}>{account.name}</option>
              ))}
            </select>
            <input name="target_weight" type="number" min="0" max="1" step="0.01" placeholder="目标权重" />
            <button type="submit"><Plus size={16} />添加</button>
          </form>
          <div className="table-list">
            {userAssets.map((asset) => (
              <div key={asset.id} className="table-row">
                <span>{asset.instrument_name}</span>
                <strong>{money(asset.market_value)}</strong>
                <small>{asset.bucket_name || '未分类'} · {asset.quantity}</small>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="panel">
        <h2>交易流水</h2>
        <form className="transaction-form" onSubmit={(event) => void submitTransaction(event)}>
          <select name="type" defaultValue="buy">
            <option value="buy">买入</option>
            <option value="sell">卖出</option>
          </select>
          <select name="instrument" required defaultValue="">
            <option value="" disabled>标的</option>
            {instruments.map((instrument) => (
              <option key={instrument.id} value={instrument.id}>{instrument.name}</option>
            ))}
          </select>
          <select name="account" defaultValue="">
            <option value="">投资账户</option>
            {investmentAccounts.map((account) => (
              <option key={account.id} value={account.id}>{account.name}</option>
            ))}
          </select>
          <select name="cash_account" defaultValue="">
            <option value="">现金账户</option>
            {cashAccounts.map((account) => (
              <option key={account.id} value={account.id}>{account.name}</option>
            ))}
          </select>
          <input name="date" type="date" defaultValue={today} />
          <input name="qty" required type="number" step="0.0001" placeholder="数量" />
          <input name="price" required type="number" step="0.0001" placeholder="价格" />
          <input name="fee" type="number" step="0.01" placeholder="手续费" defaultValue="0" />
          <input name="note" placeholder="备注" />
          <button type="submit"><Plus size={16} />记录</button>
        </form>
        <div className="transaction-list">
          {transactions.map((tx) => (
            <div key={tx.id} className="transaction-row">
              {tx.type === 'buy' ? <ArrowDownCircle size={18} /> : <ArrowUpCircle size={18} />}
              <span>{tx.instrument_name}</span>
              <strong>{tx.type === 'buy' ? '买入' : '卖出'} {tx.qty}</strong>
              <small>{money(tx.amount)} · {tx.cash_account_name || '未联动现金'}</small>
            </div>
          ))}
        </div>
      </section>
    </main>
  )
}
