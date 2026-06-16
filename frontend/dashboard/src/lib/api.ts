import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'

const api: AxiosInstance = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

let refreshPromise: Promise<string | null> | null = null

function getStoredRefreshToken(): string | null {
  return localStorage.getItem('refresh_token')
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getStoredRefreshToken()
  if (!refreshToken) return null

  try {
    const { data } = await axios.post('/api/auth/refresh', { refresh_token: refreshToken })
    const access = data.access_token as string
    localStorage.setItem('access_token', access)
    if (data.refresh_token) {
      localStorage.setItem('refresh_token', data.refresh_token as string)
    }
    api.defaults.headers.common['Authorization'] = `Bearer ${access}`
    return access
  } catch {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    return null
  }
}

const token = localStorage.getItem('access_token')
if (token) {
  api.defaults.headers.common['Authorization'] = `Bearer ${token}`
}

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const original = err.config as InternalAxiosRequestConfig & { _retry?: boolean }
    if (err.response?.status === 401 && original && !original._retry) {
      original._retry = true
      refreshPromise ??= refreshAccessToken().finally(() => {
        refreshPromise = null
      })
      const newToken = await refreshPromise
      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`
        return api(original)
      }
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api
