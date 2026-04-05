import axios from 'axios'
import { readStoredMarket } from '@/utils/market'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api',
  timeout: 10000,
})

http.interceptors.request.use((config) => {
  const market = readStoredMarket()
  config.params = {
    ...(config.params ?? {}),
    market,
  }
  return config
})

export default http
