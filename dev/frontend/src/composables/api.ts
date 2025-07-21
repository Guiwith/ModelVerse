import axios from 'axios'
import { useAuth } from './auth'
import { getApiBaseUrl, config } from '../config'

interface ItemsResponse {
  items: string[]
}

interface Resource {
  id: number
  name: string
  description: string
  resource_type: string
  status: string
  progress: number
  local_path: string | null
  error_message: string | null
  created_at: string
  updated_at: string
  // 其他字段...
}

// API组合函数
export function useApi() {
  const { getAuthHeaders } = useAuth()
  
  // 生成API URL
  const getApiUrl = (path: string) => {
    return `${getApiBaseUrl()}${config.apiBasePath}${path}`
  }

  // 获取项目列表
  const getItems = async () => {
    try {
      const response = await axios.get<ItemsResponse>(getApiUrl('/items'), {
        headers: getAuthHeaders()
      })
      return response.data.items
    } catch (error) {
      console.error('获取项目列表失败:', error)
      throw error
    }
  }

  // 获取用户列表
  const getUsers = async () => {
    try {
      const response = await axios.get(getApiUrl('/users'), {
        headers: getAuthHeaders()
      })
      return response.data
    } catch (error) {
      console.error('获取用户列表失败:', error)
      throw error
    }
  }

  // 获取资源列表
  const getResources = async (type?: string, status?: string) => {
    try {
      const params: Record<string, string> = {}
      
      if (type) params.resource_type = type
      if (status) params.status = status
      
      const response = await axios.get<Resource[]>(getApiUrl('/resources'), {
        headers: getAuthHeaders(),
        params
      })
      return response.data
    } catch (error) {
      console.error('获取资源列表失败:', error)
      throw error
    }
  }

  // 创建资源
  const createResource = async (resourceData: any) => {
    try {
      const response = await axios.post(getApiUrl('/resources'), resourceData, {
        headers: getAuthHeaders()
      })
      return response.data
    } catch (error) {
      console.error('创建资源失败:', error)
      throw error
    }
  }

  // 删除资源
  const deleteResource = async (resourceId: number) => {
    try {
      await axios.delete(getApiUrl(`/resources/${resourceId}`), {
        headers: getAuthHeaders()
      })
      return true
    } catch (error) {
      console.error('删除资源失败:', error)
      throw error
    }
  }

  // 获取镜像源列表
  const getMirrorSources = async () => {
    try {
      const response = await axios.get(getApiUrl('/mirror-sources'), {
        headers: getAuthHeaders()
      })
      return response.data
    } catch (error) {
      console.error('获取镜像源列表失败:', error)
      throw error
    }
  }

  // 搜索资源
  const searchResources = async (query: string, resourceType?: string) => {
    try {
      const params: Record<string, string> = { query }
      if (resourceType) params.resource_type = resourceType
      
      const response = await axios.get(getApiUrl('/search'), {
        headers: getAuthHeaders(),
        params
      })
      return response.data
    } catch (error) {
      console.error('搜索资源失败:', error)
      throw error
    }
  }

  // 开始下载资源
  const startDownload = async (resourceId: number, source: string) => {
    try {
      const response = await axios.post(
        getApiUrl(`/resources/${resourceId}/download`), 
        { source }, 
        { headers: getAuthHeaders() }
      )
      return response.data
    } catch (error) {
      console.error('开始下载失败:', error)
      throw error
    }
  }

  // 停止下载
  const stopDownload = async (resourceId: number) => {
    try {
      const response = await axios.post(
        getApiUrl(`/resources/${resourceId}/stop`), 
        {}, 
        { headers: getAuthHeaders() }
      )
      return response.data
    } catch (error) {
      console.error('停止下载失败:', error)
      throw error
    }
  }

  // 获取活动下载列表
  const getActiveDownloads = async () => {
    try {
      const response = await axios.get(getApiUrl('/downloads/active'), {
        headers: getAuthHeaders()
      })
      return response.data
    } catch (error) {
      console.error('获取活动下载失败:', error)
      throw error
    }
  }

  // 获取存储信息
  const getStorageInfo = async () => {
    try {
      const response = await axios.get(getApiUrl('/storage-info'), {
        headers: getAuthHeaders()
      })
      return response.data
    } catch (error) {
      console.error('获取存储信息失败:', error)
      throw error
    }
  }

  // 扫描本地资源
  const scanLocalResources = async () => {
    try {
      const response = await axios.get(getApiUrl('/resources/scan'), {
        headers: getAuthHeaders()
      })
      return response.data
    } catch (error) {
      console.error('扫描本地资源失败:', error)
      throw error
    }
  }

  // 获取用户个人资料
  const getUserProfile = async () => {
    try {
      const response = await axios.get(getApiUrl('/profile'), {
        headers: getAuthHeaders()
      })
      return response.data
    } catch (error) {
      console.error('获取用户个人资料失败:', error)
      throw error
    }
  }

  // 更新用户个人资料
  const updateUserProfile = async (profileData: {
    display_name?: string;
    email?: string;
    phone?: string;
  }) => {
    try {
      const response = await axios.put(getApiUrl('/profile'), profileData, {
        headers: getAuthHeaders()
      })
      return response.data
    } catch (error) {
      console.error('更新用户个人资料失败:', error)
      throw error
    }
  }

  // 上传用户头像
  const updateAvatar = async (formData: FormData) => {
    try {
      const response = await axios.post(getApiUrl('/profile/avatar'), formData, {
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'multipart/form-data'
        }
      })
      return response.data
    } catch (error) {
      console.error('上传头像失败:', error)
      throw error
    }
  }

  // 修改用户密码
  const changeUserPassword = async (passwordData: {
    current_password: string;
    new_password: string;
  }) => {
    try {
      const response = await axios.post(getApiUrl('/profile/change-password'), passwordData, {
        headers: getAuthHeaders()
      })
      return response.data
    } catch (error) {
      console.error('修改密码失败:', error)
      throw error
    }
  }

  // 获取管理员仪表盘数据
  const getAdminDashboard = async () => {
    try {
      const response = await axios.get(getApiUrl('/admin/dashboard'), {
        headers: getAuthHeaders()
      })
      return response.data
    } catch (error) {
      console.error('获取管理员仪表盘数据失败:', error)
      throw error
    }
  }

  // 创建新用户
  const createUser = async (userData: any) => {
    try {
      const response = await axios.post(getApiUrl('/users'), userData, {
        headers: getAuthHeaders()
      })
      return response.data
    } catch (error) {
      console.error('创建用户失败:', error)
      throw error
    }
  }

  // 删除用户
  const deleteUser = async (userId: number) => {
    try {
      await axios.delete(getApiUrl(`/users/${userId}`), {
        headers: getAuthHeaders()
      })
      return true
    } catch (error) {
      console.error('删除用户失败:', error)
      throw error
    }
  }

  // 管理员修改用户密码
  const adminChangeUserPassword = async (userId: number, newPassword: string) => {
    try {
      const response = await axios.put(
        getApiUrl(`/users/${userId}/password`), 
        { new_password: newPassword }, 
        { headers: getAuthHeaders() }
      )
      return response.data
    } catch (error) {
      console.error('修改用户密码失败:', error)
      throw error
    }
  }

  // 注册新用户
  const registerUser = async (userData: { 
    username: string; 
    password: string; 
    captcha: string; 
    captcha_id: string; 
  }) => {
    try {
      const response = await axios.post(`${getApiBaseUrl()}/api/register`, userData)
      return response.data
    } catch (error) {
      console.error('注册用户失败:', error)
      throw error
    }
  }
  
  // 获取验证码
  const getCaptcha = async () => {
    try {
      const response = await axios.get(`${getApiBaseUrl()}/api/captcha`, { responseType: 'blob' })
      const captchaId = response.headers['captcha-id']
      const captchaUrl = URL.createObjectURL(response.data as Blob)
      return { captchaId, captchaUrl }
    } catch (error) {
      console.error('获取验证码失败:', error)
      throw error
    }
  }

  return {
    getItems,
    getUsers,
    getResources,
    createResource,
    deleteResource,
    getMirrorSources,
    searchResources,
    startDownload,
    stopDownload,
    getActiveDownloads,
    getStorageInfo,
    scanLocalResources,
    getUserProfile,
    updateUserProfile,
    updateAvatar,
    changeUserPassword,
    getAdminDashboard,
    createUser,
    deleteUser,
    adminChangeUserPassword,
    registerUser,
    getCaptcha
  }
} 