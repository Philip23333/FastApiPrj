const resolveDefaultApiBaseUrl = () => {
// Use same-origin API prefix in both dev and prod.
// Dev is handled by Vite proxy, prod by Nginx reverse proxy.
return '/api'
}

const defaultApiBaseUrl = resolveDefaultApiBaseUrl()

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || defaultApiBaseUrl

export const withApiBase = (path = '') => {
	if (!path) return API_BASE_URL
	if (/^https?:\/\//i.test(path)) return path
	return path.startsWith('/') ? `${API_BASE_URL}${path}` : `${API_BASE_URL}/${path}`
}
