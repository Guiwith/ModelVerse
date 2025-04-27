import axios from 'axios'
import { ref } from 'vue'
import type { User } from '../types/models'
import { getApiBaseUrl, config } from '../config'

const TOKEN_KEY = config.storageKeys.authToken
const USER_INFO_KEY = config.storageKeys.userInfo

// 接口定义
interface LoginResponse {
  access_token: string;
  token_type: string;
}

// 状态变量
const isAuthenticated = ref(false)
const isLoading = ref(false)
const currentUser = ref<User | null>(null)
const loginError = ref('')

// 初始化验证状态
const initAuth = () => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    isAuthenticated.value = true
    // 尝试从本地存储获取用户信息
    const userInfo = localStorage.getItem(USER_INFO_KEY)
    if (userInfo) {
      try {
        currentUser.value = JSON.parse(userInfo)
      } catch (e) {
        console.error('解析用户信息失败', e)
      }
    }
  }
}

// 身份验证钩子
export function useAuth() {
  // 登录方法
  const login = async (username: string, password: string) => {
    isLoading.value = true
    loginError.value = ''
    try {
      // 构建API URL
      const apiUrl = `${getApiBaseUrl()}/token`
      
      // 创建FormData
      const formData = new URLSearchParams()
      formData.append('username', username)
      formData.append('password', password)
      
      // 发送请求
      const response = await axios.post<LoginResponse>(apiUrl, formData)
      const { access_token } = response.data
      
      // 存储token
      localStorage.setItem(TOKEN_KEY, access_token)
      isAuthenticated.value = true
      
      // 获取用户信息
      await fetchUserInfo()
      
      return true
    } catch (error: any) {
      console.error('登录失败：', error)
      loginError.value = error.response?.data?.detail || '登录失败，请检查用户名和密码'
      return false
    } finally {
      isLoading.value = false
    }
  }

  // 获取用户信息
  const fetchUserInfo = async () => {
    try {
      const token = localStorage.getItem(TOKEN_KEY)
      if (!token) return null
      
      const response = await axios.get<User>(`${getApiBaseUrl()}${config.apiBasePath}/users/me`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      currentUser.value = response.data
      localStorage.setItem(USER_INFO_KEY, JSON.stringify(response.data))
      return response.data
    } catch (error) {
      console.error('获取用户信息失败：', error)
      logout()
      return null
    }
  }

  // 注销方法
  const logout = () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_INFO_KEY)
    isAuthenticated.value = false
    currentUser.value = null
  }

  // 获取认证头部
  const getAuthHeaders = () => {
    const token = localStorage.getItem(TOKEN_KEY)
    return {
      'Authorization': `Bearer ${token}`
    }
  }

  // 检查是否是管理员
  const isAdmin = () => {
    return currentUser.value?.is_admin === true
  }

  return {
    isAuthenticated,
    isLoading,
    currentUser,
    loginError,
    login,
    logout,
    getAuthHeaders,
    fetchUserInfo,
    isAdmin,
    initAuth
  }
} 