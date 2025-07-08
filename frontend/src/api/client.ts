import axios from 'axios'

// 创建axios实例，设置基础URL和超时时间
const apiClient = axios.create({
  baseURL: 'http://172.31.118.255:8000',  // 后端地址
  timeout: 60000, // 增加超时时间到60秒，因为资源下载可能需要更长时间的响应
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
})

// 请求拦截器 - 添加认证令牌
apiClient.interceptors.request.use(
  config => {
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    
    // 确保所有请求都有/api前缀，除非是完整URL或已经有/api前缀
    // 排除登录接口 /token
    if (config.url && 
        !config.url.startsWith('http') && 
        !config.url.startsWith('/api') && 
        config.url !== '/token') {
      config.url = `/api${config.url}`
    }
    
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器 - 处理常见错误
apiClient.interceptors.response.use(
  response => {
    return response
  },
  error => {
    // 未授权处理 (401) - 清除token并重定向到登录页
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('user_info')
      // 如果不是登录页面，则重定向到登录页
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    
    return Promise.reject(error)
  }
)

// 授权相关方法
const auth = {
  // 登录方法
  login(username, password) {
    const formData = new FormData()
    formData.append('username', username)
    formData.append('password', password)
    
    return apiClient.post('/token', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      baseURL: 'http://172.31.118.255:8000'  // 覆盖基础URL，因为token接口在根目录
    })
  },
  
  // 注册方法
  register(userData) {
    return apiClient.post('/users/register', userData)
  }
}

// 用户相关方法
const users = {
  // 获取当前用户信息
  getCurrentUser() {
    return apiClient.get('/users/me')
  },
  
  // 更新用户资料
  updateProfile(profileData) {
    return apiClient.put('/users/me/profile', profileData)
  },
  
  // 修改密码
  changePassword(passwordData) {
    return apiClient.put('/users/me/password', passwordData)
  },
  
  // 获取所有用户 (仅管理员)
  getAllUsers() {
    return apiClient.get('/users')
  }
}

// 训练相关方法
const training = {
  // 获取所有训练任务
  getTasks() {
    return apiClient.get('/training/tasks')
  },
  
  // 获取单个训练任务详情
  getTaskById(id: string | number) {
    return apiClient.get(`/training/tasks/${id}`)
  },
  
  // 创建新训练任务
  createTask(taskData: {
    name: string;
    base_model_id: number;
    dataset_id: number;
    config_params?: Record<string, any>;
  }) {
    return apiClient.post('/training/tasks', taskData)
  },
  
  // 开始训练任务
  startTask(id: string | number) {
    return apiClient.post(`/training/tasks/${id}/start`)
  },
  
  // 停止训练任务
  stopTask(id: string | number) {
    return apiClient.post(`/training/tasks/${id}/stop`)
  },
  
  // 删除训练任务
  deleteTask(id: string | number) {
    return apiClient.delete(`/training/tasks/${id}`)
  },
  
  // 获取训练日志
  getLogs(id: string | number, limit: number = 100, offset: number = 0) {
    return apiClient.get(`/training/tasks/${id}/logs`, {
      params: { limit, offset }
    })
  },
  
  // 获取可用的模型列表
  getAvailableModels() {
    return apiClient.get('/training/available-models')
  },
  
  // 获取可用的数据集列表
  getAvailableDatasets() {
    return apiClient.get('/training/available-datasets')
  },
  
  // 获取默认训练配置
  getDefaultConfig() {
    return apiClient.get('/training/default-config')
  }
}

// 资源相关方法
const resources = {
  // 获取所有资源
  getAll() {
    return apiClient.get('/resources')
  },
  
  // 创建新资源
  create(resourceData) {
    return apiClient.post('/resources', resourceData)
  },
  
  // 获取单个资源详情
  getById(id) {
    return apiClient.get(`/resources/${id}`)
  },
  
  // 请求下载资源
  download(id, source = 'OFFICIAL') {
    return apiClient.post(`/resources/${id}/download`, { source })
  },
  
  // 取消下载
  cancelDownload(id) {
    return apiClient.post(`/resources/${id}/stop`)
  },
  
  // 重试下载
  retryDownload(id, source = 'OFFICIAL') {
    return apiClient.post(`/resources/${id}/retry`, { source })
  },
  
  // 删除资源
  delete(id) {
    return apiClient.delete(`/resources/${id}`)
  },
  
  // 获取资源下载进度
  getProgress(id) {
    return apiClient.get(`/resources/${id}/progress`)
  },
  
  // 扫描本地资源 (此API不需要身份验证)
  scanLocalResources() {
    return apiClient.get('/resources/scan')
  }
}

// 检查服务器状态
const checkServerStatus = () => {
  return apiClient.get('/health')
}

// 推理相关方法
const inference = {
  // 获取所有推理任务
  getTasks() {
    return apiClient.get('/inference/tasks')
  },
  
  // 获取单个推理任务详情
  getTask(id: string | number) {
    return apiClient.get(`/inference/tasks/${id}`)
  },
  
  // 创建新推理任务
  createTask(taskData: {
    name: string;
    model_id: number;
    tensor_parallel_size?: number;
    max_model_len?: number;
    quantization?: string;
    max_tokens?: number;
    temperature?: number;
    top_p?: number;
    top_k?: number;
    repetition_penalty?: number;
  }) {
    return apiClient.post('/inference/tasks', taskData)
  },
  
  // 启动推理任务
  startTask(id: string | number) {
    return apiClient.post(`/inference/tasks/${id}/start`)
  },
  
  // 停止推理任务
  stopTask(id: string | number) {
    return apiClient.post(`/inference/tasks/${id}/stop`)
  },
  
  // 删除推理任务
  deleteTask(id: string | number) {
    return apiClient.delete(`/inference/tasks/${id}`)
  },
  
  // 更新推理参数
  updateParams(id: string | number, params: any) {
    return apiClient.put(`/inference/tasks/${id}/params`, params)
  },
  
  // 获取聊天记录
  getChatHistory(id: string | number) {
    return apiClient.get(`/inference/tasks/${id}/chat`)
  },
  
  // 发送聊天消息
  sendMessage(id: string | number, messages: any[], params?: any) {
    return apiClient.post(`/inference/tasks/${id}/chat`, { 
      messages,
      ...params
    })
  },
  
  // 获取GPU状态
  getGpuStatus() {
    return apiClient.get('/inference/gpu')
  }
}

// 评估相关方法
const evaluation = {
  // 获取所有评估任务
  getTasks() {
    return apiClient.get('/evaluation/tasks')
  },
  
  // 获取单个评估任务详情
  getTaskById(id: string | number) {
    return apiClient.get(`/evaluation/tasks/${id}`)
  },
  
  // 创建新评估任务
  createTask(taskData: {
    name: string;
    model_id: number;
    benchmark_type: string;
    num_fewshot?: number;
    custom_dataset_path?: string;
  }) {
    return apiClient.post('/evaluation/tasks', taskData)
  },
  
  // 开始评估任务
  startTask(id: string | number) {
    return apiClient.post(`/evaluation/tasks/${id}/start`)
  },
  
  // 停止评估任务
  stopTask(id: string | number) {
    return apiClient.post(`/evaluation/tasks/${id}/stop`)
  },
  
  // 删除评估任务
  deleteTask(id: string | number) {
    return apiClient.delete(`/evaluation/tasks/${id}`)
  },
  
  // 获取评估日志
  getLogs(id: string | number, limit: number = 100, offset: number = 0) {
    return apiClient.get(`/evaluation/tasks/${id}/logs`, {
      params: { limit, offset }
    })
  },
  
  // 获取可用的基准测试
  getBenchmarks() {
    return apiClient.get('/evaluation/benchmarks')
  }
}

// 统一导出所有模块
export { apiClient, auth, users, training, resources, inference, evaluation, checkServerStatus } 