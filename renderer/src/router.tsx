import { createBrowserRouter } from 'react-router-dom'
import App from './App'
import { AssetsPage } from './pages/Assets'
import { Dashboard } from './pages/Dashboard'
import { HistoryPage } from './pages/History'
import { LedgerPage } from './pages/Ledger'
import { RebalanceHistoryPage } from './pages/RebalanceHistory'
import { RebalancePage } from './pages/Rebalance'

export const router = createBrowserRouter([
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
])
