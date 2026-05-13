import { BarChart3, History, LogOut, Repeat2, ReceiptText, TrendingUp, WalletCards } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from './auth/useAuth'
import './App.css'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: BarChart3, end: true },
  { to: '/assets', label: '配置', icon: WalletCards, end: false },
  { to: '/ledger', label: '账单', icon: ReceiptText, end: false },
  { to: '/rebalance', label: '再平衡', icon: Repeat2, end: false },
  { to: '/history', label: '收益曲线', icon: TrendingUp, end: false },
  { to: '/rebalance/history', label: '再平衡记录', icon: History, end: false },
]

function App() {
  const { user, logout } = useAuth()

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">B</span>
          <div>
            <strong>Brown</strong>
            <small>永久组合</small>
          </div>
        </div>
        <nav aria-label="主导航">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                className={({ isActive }) => (isActive ? 'nav-button nav-button-active' : 'nav-button')}
                key={item.to}
                to={item.to}
                end={item.end}
              >
                <Icon size={18} />
                {item.label}
              </NavLink>
            )
          })}
        </nav>
        <div className="sidebar-account">
          <span>{user?.name || user?.email}</span>
          <button className="icon-button" type="button" onClick={logout} aria-label="退出登录">
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}

export default App
