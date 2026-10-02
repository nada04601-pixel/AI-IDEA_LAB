import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface User {
  id: string
  email: string
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const isAuthenticated = ref(false)

  function setUser(newUser: User | null) {
    user.value = newUser
    isAuthenticated.value = !!newUser
  }

  function clearUser() {
    user.value = null
    isAuthenticated.value = false
  }

  return {
    user,
    isAuthenticated,
    setUser,
    clearUser,
  }
})
