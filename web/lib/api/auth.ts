import type { User } from '../types'
import { apiClient } from './http'

export async function login(email: string, password: string) {
  const { data } = await apiClient.axios.post('/console/api/auth/signin', { email, password })
  return data.data
}

export async function signup(email: string, password: string, name: string, interfaceLanguage?: string) {
  const { data } = await apiClient.axios.post('/console/api/auth/signup', {
    email,
    password,
    name,
    ...(interfaceLanguage ? { interface_language: interfaceLanguage } : {}),
  })
  return data.data
}

export async function logout() {
  const { data } = await apiClient.axios.post('/console/api/auth/logout')
  return data
}

export async function getCurrentUser(): Promise<User> {
  const { data } = await apiClient.axios.get('/console/api/auth/me')
  return data.data.account
}
