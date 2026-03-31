import { ref } from 'vue'
import { useRouter } from 'vue-router'

export function useTopNavAuth() {
  const router = useRouter()
  const currentUser = ref(null)

  const getToken = () => localStorage.getItem('accessToken')

  const isTokenExpired = (token) => {
    if (!token) return true
    try {
      const parts = token.split('.')
      if (parts.length < 2) return true
      const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
      const payload = JSON.parse(decodeURIComponent(escape(window.atob(base64))))
      const exp = Number(payload?.exp)
      if (!exp) return true
      return Date.now() >= exp * 1000
    } catch (e) {
      return true
    }
  }

  const clearAuthStorage = () => {
    localStorage.removeItem('accessToken')
    localStorage.removeItem('currentUser')
  }

  const restoreCurrentUser = () => {
    const savedUser = localStorage.getItem('currentUser')
    const token = getToken()
    if (!savedUser || !token || isTokenExpired(token)) {
      currentUser.value = null
      clearAuthStorage()
      return null
    }

    try {
      currentUser.value = JSON.parse(savedUser)
      return currentUser.value
    } catch (e) {
      currentUser.value = null
      clearAuthStorage()
      return null
    }
  }

  const handleAuthSuccess = ({ user, accessToken }) => {
    currentUser.value = user || null
    if (accessToken) {
      localStorage.setItem('accessToken', accessToken)
    }
    localStorage.setItem('currentUser', JSON.stringify(currentUser.value))
  }

  const logout = (redirectPath = '/') => {
    currentUser.value = null
    clearAuthStorage()
    if (redirectPath) {
      router.push(redirectPath)
    }
  }

  const goHome = () => {
    router.push('/')
  }

  const goToProfile = () => {
    router.push('/profile')
  }

  const handlePublishClick = ({ openLoginModal } = {}) => {
    if (!currentUser.value) {
      if (typeof openLoginModal === 'function') {
        openLoginModal()
      } else {
        router.push('/')
      }
      return
    }
    router.push('/publish')
  }

  const ensureAuthenticated = (redirectPath = '/') => {
    const token = getToken()
    if (!currentUser.value || !token || isTokenExpired(token)) {
      currentUser.value = null
      clearAuthStorage()
      window.dispatchEvent(new CustomEvent('auth-required', {
        detail: {
          message: '请先登录后再继续操作。',
          reason: 'guard-check',
        }
      }))
      if (redirectPath) {
        router.push(redirectPath)
      }
      return false
    }
    return true
  }

  return {
    currentUser,
    restoreCurrentUser,
    handleAuthSuccess,
    logout,
    goHome,
    goToProfile,
    handlePublishClick,
    ensureAuthenticated,
  }
}
