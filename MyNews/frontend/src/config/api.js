const rawBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api'

export const API_BASE_URL = rawBaseUrl.replace(/\/$/, '')

export const withApiBase = (path = '') => {
	const safePath = path.startsWith('/') ? path : `/${path}`
	return `${API_BASE_URL}${safePath}`
}
