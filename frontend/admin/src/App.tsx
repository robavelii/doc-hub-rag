import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Tenants from './pages/Tenants'
import TenantDetail from './pages/TenantDetail'
import GlobalUsage from './pages/GlobalUsage'

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ padding: '2rem' }}>
        <h1 style={{ color: 'var(--primary)', marginBottom: '2rem' }}>Superadmin Panel</h1>
        <Routes>
          <Route path="/" element={<Tenants />} />
          <Route path="/tenants/:id" element={<TenantDetail />} />
          <Route path="/usage" element={<GlobalUsage />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
