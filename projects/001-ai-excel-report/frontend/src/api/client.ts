import axios, { type AxiosError } from 'axios'
import { ElMessage } from 'element-plus'

export interface ApiErrorResponse {
  error: {
    code: string
    message: string
    details?: Record<string, unknown>
  }
}

const apiClient = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Enable mock mode for live preview and walkthrough
import { setupMock } from './mock'
setupMock(apiClient)

// Response Interceptor for Error Handling
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorResponse>) => {
    if (error.response) {
      const status = error.response.status
      const data = error.response.data

      if (status === 401) {
        if (!window.location.pathname.startsWith('/login')) {
          ElMessage.error('로그인이 필요하거나 세션이 만료되었습니다.')
          window.location.href = '/login'
        }
      } else if (data?.error?.message) {
        ElMessage.error(data.error.message)
      } else {
        ElMessage.error(`요청 처리 중 오류가 발생했습니다. (${status})`)
      }
    } else {
      ElMessage.error('서버와 통신할 수 없습니다. 네트워크 상태를 확인해주세요.')
    }
    return Promise.reject(error)
  }
)

export default apiClient
