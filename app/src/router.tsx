import { createBrowserRouter } from 'react-router-dom'
import App from './App'
import { RequireAuth } from './auth/RequireAuth'
import { LoginPage } from './pages/Login'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      { path: '/', element: <App /> },
    ],
  },
])
