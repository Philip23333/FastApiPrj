import { createApp } from 'vue'
import axios from 'axios'
import './style.css'
import App from './App.vue'
import router from './router'
// 目标：所有 axios 请求自动携带 localStorage 中的 accessToken
// 效果：开发者无需在每个请求中手动写 headers: { Authorization: 'Bearer xxx' }
// Register once: attach access token from localStorage to all axios requests.
if (!axios.__authInterceptorRegistered) {
	axios.interceptors.request.use(
		(config) => {
			const token = localStorage.getItem('accessToken')
			if (token) {
				config.headers = config.headers || {}
				if (!config.headers.Authorization) {
					config.headers.Authorization = `Bearer ${token}`
				}
			}
			return config
		},
		(error) => Promise.reject(error)
	)
	axios.__authInterceptorRegistered = true
}

// 统一处理 token 失效，避免 UI 仍显示“已登录”但接口持续 401。
if (!axios.__auth401InterceptorRegistered) {
	axios.interceptors.response.use(
		(response) => response,
		(error) => {
			if (error?.response?.status === 401) {
				localStorage.removeItem('accessToken')
				localStorage.removeItem('currentUser')
				window.dispatchEvent(new CustomEvent('auth-required', {
					detail: {
						message: '登录状态已失效，请重新登录。',
						reason: 'http-401',
					}
				}))
			}
			return Promise.reject(error)
		}
	)
	axios.__auth401InterceptorRegistered = true
}

const app = createApp(App)
app.use(router)
app.mount('#app')

