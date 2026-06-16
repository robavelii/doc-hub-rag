import axios, { type AxiosInstance } from 'axios'

const adminApi: AxiosInstance = axios.create({ baseURL: '/api' })

const token = localStorage.getItem('access_token')
if (token) {
  adminApi.defaults.headers.common['Authorization'] = `Bearer ${token}`
}

export default adminApi
