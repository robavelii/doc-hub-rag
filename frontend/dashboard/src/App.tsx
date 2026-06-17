import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import { ThemeProvider } from './theme/ThemeProvider'
import { ToastProvider } from './components/ui'
import Onboarding from './components/Onboarding'
import Login from './pages/Login'
import Register from './pages/Register'
import Documents from './pages/Documents'
import Chat from './pages/Chat'
import Usage from './pages/Usage'
import Widget from './pages/Widget'
import Settings from './pages/Settings'
import Integrations from './pages/Integrations'
import AdminTenants from './pages/admin/AdminTenants'
import AdminTenantDetail from './pages/admin/AdminTenantDetail'
import AdminGlobalUsage from './pages/admin/AdminGlobalUsage'
import Layout from './components/Layout'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const accessToken = useAuthStore((s) => s.accessToken) || localStorage.getItem('access_token')
  return accessToken ? <>{children}</> : <Navigate to="/login" />
}

function SuperAdminRoute({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user)
  if (!user?.is_superadmin) return <Navigate to="/chat" />
  return <>{children}</>
}

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, '') || undefined}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route
              path="/*"
              element={
                <PrivateRoute>
                  <Layout>
                    <Onboarding />
                    <Routes>
                      <Route path="/" element={<Navigate to="/chat" />} />
                      <Route path="/chat" element={<Chat />} />
                      <Route path="/documents" element={<Documents />} />
                      <Route path="/usage" element={<Usage />} />
                      <Route path="/widget" element={<Widget />} />
                      <Route path="/integrations" element={<Integrations />} />
                      <Route path="/settings" element={<Settings />} />
                      <Route path="/admin/tenants" element={<SuperAdminRoute><AdminTenants /></SuperAdminRoute>} />
                      <Route path="/admin/tenants/:id" element={<SuperAdminRoute><AdminTenantDetail /></SuperAdminRoute>} />
                      <Route path="/admin/usage" element={<SuperAdminRoute><AdminGlobalUsage /></SuperAdminRoute>} />
                    </Routes>
                  </Layout>
                </PrivateRoute>
              }
            />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </ThemeProvider>
  )
}
