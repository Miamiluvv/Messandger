import { create } from 'zustand'
import api from '../api/axios'

export const useAuthStore = create((set, get) => ({
  token: localStorage.getItem('token') || null,
  user: null,
  loading: false,

  login: async (email, password) => {
    set({ loading: true })
    try {
      const res = await api.post('/auth/login', { email, password })
      const { access_token, password_expired } = res.data
      localStorage.setItem('token', access_token)
      set({ token: access_token, loading: false })
      await get().fetchUser()
      return { success: true, password_expired }
    } catch (error) {
      set({ loading: false })
      return { success: false, error: error.response?.data?.detail || 'Ошибка входа' }
    }
  },

  fetchUser: async () => {
    try {
      const res = await api.get('/auth/me')
      set({ user: res.data })
    } catch (error) {
      console.error('Ошибка загрузки профиля:', error)
    }
  },

  logout: () => {
    localStorage.removeItem('token')
    set({ token: null, user: null })
    window.location.href = '/login'
  },

  changePassword: async (oldPassword, newPassword) => {
    try {
      await api.put('/auth/me/password', { old_password: oldPassword, new_password: newPassword })
      return { success: true }
    } catch (error) {
      return { success: false, error: error.response?.data?.detail || 'Ошибка' }
    }
  },
}))
