import axios from 'axios'

// 创建axios实例
export const apiClient = axios.create({
  baseURL: 'http://172.31.118.255:8000',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
})

// 请求拦截器
apiClient.interceptors.request.use(
  config => {
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  error => Promise.reject(error)
)

// 响应拦截器
apiClient.interceptors.response.use(
  response => response,
  error => {
    // 处理401错误
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('user_info')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

// 创建共享API专用的axios实例，不添加验证令牌
export const sharedApiClient = axios.create({
  baseURL: 'http://172.31.118.255:8000',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
})

// 推理API
export const inference = {
  // 获取推理任务列表
  getTasks: () => {
    return apiClient.get('/api/inference/tasks')
  },
  
  // 获取推理任务详情
  getTask: (taskId) => {
    return apiClient.get(`/api/inference/tasks/${taskId}`)
  },
  
  // 创建推理任务
  createTask: (taskData) => {
    return apiClient.post('/api/inference/tasks', taskData)
  },
  
  // 删除推理任务
  deleteTask: (taskId) => {
    return apiClient.delete(`/api/inference/tasks/${taskId}`)
  },
  
  // 启动推理任务
  startTask: (taskId) => {
    return apiClient.post(`/api/inference/tasks/${taskId}/start`)
  },
  
  // 停止推理任务
  stopTask: (taskId) => {
    return apiClient.post(`/api/inference/tasks/${taskId}/stop`)
  },
  
  // 获取推理任务状态
  getTaskStatus: (taskId) => {
    return apiClient.get(`/api/inference/tasks/${taskId}/status`)
  },
  
  // 获取GPU状态
  getGpuStatus: () => {
    return apiClient.get('/api/inference/gpu')
  },
  
  // 聊天接口
  chat: (taskId, messages, params = {}) => {
    return apiClient.post(`/api/inference/tasks/${taskId}/chat`, {
      messages,
      task_id: taskId,
      ...params
    })
  },
  
  // 更新推理参数
  updateParams: (taskId, params) => {
    return apiClient.put(`/api/inference/tasks/${taskId}/params`, params)
  },
  
  // 切换共享状态
  toggleShareStatus: (taskId, shareEnabled, displayName = null) => {
    console.log('调用toggleShareStatus API:', {
      url: `/api/inference/tasks/${taskId}/toggle-share`,
      data: {
        share_enabled: shareEnabled,
        display_name: displayName
      },
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
        'Content-Type': 'application/json'
      }
    });
    
    return apiClient.post(`/api/inference/tasks/${taskId}/toggle-share`, {
      share_enabled: shareEnabled,
      display_name: displayName
    });
  }
}

// 训练API
export const training = {
  // 获取所有训练任务
  getTasks: () => {
    return apiClient.get('/api/training/tasks')
  },
  
  // 获取单个训练任务详情
  getTaskById: (id) => {
    return apiClient.get(`/api/training/tasks/${id}`)
  },
  
  // 创建新训练任务
  createTask: (taskData) => {
    return apiClient.post('/api/training/tasks', taskData)
  },
  
  // 开始训练任务
  startTask: (id) => {
    return apiClient.post(`/api/training/tasks/${id}/start`)
  },
  
  // 停止训练任务
  stopTask: (id) => {
    return apiClient.post(`/api/training/tasks/${id}/stop`)
  },
  
  // 删除训练任务
  deleteTask: (id) => {
    return apiClient.delete(`/api/training/tasks/${id}`)
  },
  
  // 获取训练日志
  getLogs: (id, limit = 100, offset = 0) => {
    return apiClient.get(`/api/training/tasks/${id}/logs`, {
      params: { limit, offset }
    })
  }
}

// 共享API
export const sharedInference = {
  // 获取共享推理任务列表
  getTasks: () => {
    // 直接使用简化API路径
    return sharedApiClient.get('/api/share');
  },
  
  // 获取共享推理任务详情
  getTask: (taskId) => {
    // 直接使用简化API路径
    return sharedApiClient.get(`/api/share/${taskId}`);
  }
} 