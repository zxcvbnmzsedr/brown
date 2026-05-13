import { createBrowserRouter } from 'react-router-dom'
import App from './App'
import { RequireAuth } from './auth/RequireAuth'
import { AssetsPage } from './pages/Assets'
import { Dashboard } from './pages/Dashboard'
import { HistoryPage } from './pages/History'
import { LedgerPage } from './pages/Ledger'
import { LoginPage } from './pages/Login'
import { RebalanceHistoryPage } from './pages/RebalanceHistory'
import { RebalancePage } from './pages/Rebalance'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        path: '/',
        element: <App />,
        children: [
          { index: true, element: <Dashboard /> },
          { path: 'assets', element: <AssetsPage /> },
          { path: 'ledger', element: <LedgerPage /> },
          { path: 'rebalance', element: <RebalancePage /> },
          { path: 'history', element: <HistoryPage /> },
          { path: 'rebalance/history', element: <RebalanceHistoryPage /> },
        ],
      },
    ],
  },
])
