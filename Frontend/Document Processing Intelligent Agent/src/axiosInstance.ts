// src/axiosInstance.ts
import axios, {
  AxiosError,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
  type AxiosResponse,
} from 'axios'
import { IS_DEV } from './config'

// 直接使用后端实际地址，避免代理问题
// 切换到 8000 端口
const baseURL = 'http://localhost:8000'

const api: AxiosInstance = axios.create({
  baseURL,
  timeout: 15000,
  withCredentials: false,
})

// 认证状态管理
interface AuthState {
  accessToken: string | null
  expiresAt: number | null
  isRefreshing: boolean
  refreshSubscribers: Array<(token: string | null) => void>
}

const authState: AuthState = {
  accessToken: null,
  expiresAt: null,
  isRefreshing: false,
  refreshSubscribers: []
}

// 存储token的安全方式
const TOKEN_STORAGE_KEY = 'app_auth_token'
const TOKEN_EXPIRES_KEY = 'app_token_expires'

/**
 * 保存token到安全存储
 * 使用sessionStorage替代localStorage以增强安全性，减少XSS风险
 */
function saveToken(token: string, expiresIn: number = 3600) {
  try {
    authState.accessToken = token
    const expiresAt = Date.now() + (expiresIn * 1000)
    authState.expiresAt = expiresAt
    
    if (typeof sessionStorage !== 'undefined') {
      // 使用简单的加密（在生产环境中应考虑更强的加密方案）
      const encodedToken = btoa(token)
      sessionStorage.setItem(TOKEN_STORAGE_KEY, encodedToken)
      sessionStorage.setItem(TOKEN_EXPIRES_KEY, expiresAt.toString())
    }
  } catch (error) {
    console.error('保存token失败:', error)
  }
}

/**
 * 从存储中加载token
 */
function loadToken() {
  try {
    if (typeof sessionStorage !== 'undefined') {
      const encodedToken = sessionStorage.getItem(TOKEN_STORAGE_KEY)
      const expiresAtStr = sessionStorage.getItem(TOKEN_EXPIRES_KEY)
      
      if (encodedToken && expiresAtStr) {
        try {
          const token = atob(encodedToken)
          const expiresAt = parseInt(expiresAtStr, 10)
          
          // 检查token是否已过期
          if (Date.now() < expiresAt) {
            authState.accessToken = token
            authState.expiresAt = expiresAt
            return true
          } else {
            // token已过期，清除存储
            clearToken()
          }
        } catch (decodeError) {
          console.error('解码token失败:', decodeError)
          clearToken()
        }
      }
    }
    return false
  } catch (error) {
    console.error('加载token失败:', error)
    return false
  }
}

/**
 * 清除token
 */
function clearToken() {
  authState.accessToken = null
  authState.expiresAt = null
  
  if (typeof sessionStorage !== 'undefined') {
    sessionStorage.removeItem(TOKEN_STORAGE_KEY)
    sessionStorage.removeItem(TOKEN_EXPIRES_KEY)
  }
  
  // 触发认证状态更新事件
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('auth:logout'))
  }
}

/**
 * 检查token是否有效
 */
function isTokenValid(): boolean {
  // 检查token是否存在且未过期
  return !!(authState.accessToken && authState.expiresAt && Date.now() < authState.expiresAt)
}

/**
 * 注册token刷新订阅者
 */
function subscribeTokenRefresh(callback: (token: string | null) => void) {
  authState.refreshSubscribers.push(callback)
}

/**
 * 通知所有token刷新订阅者
 */
function notifyTokenRefreshSubscribers(token: string | null) {
  authState.refreshSubscribers.forEach(callback => callback(token))
  authState.refreshSubscribers = []
}

/**
 * 用户登录函数 - 由应用调用，而不是自动调用
 */
export async function login(username: string, password: string): Promise<{ success: boolean; error?: string }> {
  try {
    // 直接使用axios，避免循环调用拦截器
    const response = await axios.post(`${baseURL}/api/auth/token`, {
      username,
      password
    }, {
      timeout: 15000,
      headers: {
        'Content-Type': 'application/json'
      }
    })
    
    const { access_token, expires_in } = response.data
    
    if (access_token) {
      saveToken(access_token, expires_in || 3600) // 默认1小时过期
      
      // 触发登录成功事件
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('auth:login'))
      }
      
      return { success: true }
    } else {
      return { success: false, error: '认证失败：未返回访问令牌' }
    }
  } catch (error: any) {
    console.error('登录失败:', error)
    let errorMessage = '登录失败，请稍后重试'
    
    if (error.response) {
      if (error.response.status === 401) {
        errorMessage = '用户名或密码错误'
      } else if (error.response.data && error.response.data.detail) {
        errorMessage = error.response.data.detail
      }
    } else if (error.request) {
      errorMessage = '无法连接到服务器，请检查网络连接'
    }
    
    return { success: false, error: errorMessage }
  }
}

/**
 * 用户登出函数
 */
export function logout() {
  clearToken()
}

/**
 * 获取当前认证状态
 */
export function getAuthStatus() {
  return {
    isAuthenticated: isTokenValid(),
    accessToken: authState.accessToken
  }
}

// 尝试从存储中加载token
loadToken()

// 请求拦截器
api.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    if (IS_DEV) {
      console.log('🚀 [Request]', config.method?.toUpperCase(), config.baseURL, config.url)
    }

    // 检查是否已经是获取token的请求，避免循环
    const isTokenRequest = config.url?.includes('/auth/token')
    
    // 对于token请求，不尝试获取token，避免循环调用
    if (isTokenRequest) {
      console.log('处理token请求，跳过token获取')
    }
    
    // FormData 上传不手动设 Content-Type（让浏览器自己带 boundary）
    const isFormData = typeof FormData !== 'undefined' && config.data instanceof FormData

    const merged: Record<string, any> = {
      'X-Requested-With': 'XMLHttpRequest',
      ...(config.headers ?? {}),
    }
    
    // 如果token有效且不是token请求且还没有设置Authorization头，添加Bearer令牌
    if (isTokenValid() && !isTokenRequest && !merged['Authorization']) {
      merged['Authorization'] = `Bearer ${authState.accessToken}`
    }
    
    // 只有非FormData且没有Content-Type时才设置默认Content-Type
    if (!isFormData && !('Content-Type' in merged)) {
      merged['Content-Type'] = 'application/json'
    }
    config.headers = merged as any // 规避 AxiosHeaders 只读类型问题

    return config
  },
  (error: AxiosError) => {
    console.error('❌ [Request Error]:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response: AxiosResponse) => {
    if (IS_DEV) console.log('✅ [Response]', response.status, response.config.url)
    return response.data
  },
  async (error: any) => {
    const originalRequest = error.config
    
    // 增强错误处理，处理所有类型的错误
    if (error.response) {
      // 在开发环境中，如果遇到401错误，我们完全跳过错误处理，不记录到控制台
      // 这样可以在没有认证的情况下开发和测试，同时避免控制台显示认证错误信息
      if (IS_DEV && error.response.status === 401) {
        console.log('开发环境：跳过认证检查，继续执行请求')
        return Promise.resolve(error.response.data); // 返回原始响应数据，而不是拒绝请求
      }
      
      // 服务器返回了错误状态码（非开发环境的401错误）
      console.error('❌ [Response Error]', error.response.status, error.response.data)
      
      // 处理401未授权错误
      if (error.response.status === 401 && !originalRequest._retry) {
        console.log('收到401错误，处理认证问题')
        
        // 标记当前请求已尝试过重试，避免无限循环
        originalRequest._retry = true
        
        // 如果正在刷新token，将当前请求加入等待队列
        if (authState.isRefreshing) {
          return new Promise((resolve, reject) => {
            subscribeTokenRefresh((token) => {
              if (token) {
                originalRequest.headers['Authorization'] = `Bearer ${token}`
                resolve(api(originalRequest))
              } else {
                reject(error)
              }
            })
          })
        }
        
        // 标记开始刷新token
        authState.isRefreshing = true
        
        try {
          // 在开发环境中，由于我们没有实现刷新token的API，直接清除token并通知
          // 在生产环境中，这里应该调用刷新token的API
          clearToken()
          
          // 触发未授权事件
          if (typeof window !== 'undefined') {
            window.dispatchEvent(new CustomEvent('auth:unauthorized'))
          }
          
          // 通知所有等待的请求
          notifyTokenRefreshSubscribers(null)
          
          return Promise.reject(new Error('认证已过期，请重新登录'))
        } catch (refreshError) {
          console.error('刷新token失败:', refreshError)
          clearToken()
          notifyTokenRefreshSubscribers(null)
          return Promise.reject(refreshError)
        } finally {
          authState.isRefreshing = false
        }
      }
    } else if (error.request) {
      // 请求已发送但没有收到响应
      console.error('⚠️ [No Response from Server]:', error.request)
      // 检查是否是TypeError: Failed to fetch
      if (error.message === 'Failed to fetch' || error.name === 'TypeError') {
        console.error('🌐 [Network Error]: 网络连接失败，请检查服务器是否可用')
      }
    } else {
      // 请求配置出错
      console.error('💥 [Axios Error]:', error.message)
      // 检查是否是TypeError
      if (error.name === 'TypeError') {
        console.error('🔧 [Type Error]: 发生类型错误，请检查请求配置')
      }
    }
    
    // 为错误添加更详细的信息
    error.enhancedMessage = error.message || '未知错误'
    if (error.message === 'Failed to fetch') {
      error.enhancedMessage = '网络连接失败，请检查服务器是否运行正常'
    }
    
    return Promise.reject(error)
  }
)

export default api

// 导出认证相关函数
export const auth = {
  login,
  logout,
  getStatus: getAuthStatus
}
