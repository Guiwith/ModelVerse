<template>
  <div class="inference-page">
    <div class="page-header">
      <h1>推理模型管理</h1>
      <button @click="openCreateModal" class="btn btn-primary">
        <span class="material-icons">add</span>
        新建推理任务
      </button>
    </div>

    <div class="gpu-status" v-if="gpuInfo">
      <h3>GPU状态</h3>
      <div class="gpu-cards">
        <div v-for="(gpu, index) in gpuInfo.gpus" :key="index" class="gpu-card">
          <div class="gpu-name">{{ gpu.name }}</div>
          <div class="gpu-memory">
            <div class="progress">
              <div class="progress-bar" :style="{ width: (gpu.memory_used / gpu.memory_total * 100) + '%' }"></div>
            </div>
            <div class="memory-text">
              已用: {{ formatMemory(gpu.memory_used) }} / {{ formatMemory(gpu.memory_total) }}
            </div>
          </div>
        </div>
      </div>
      <div class="gpu-summary">
        <div>总显存: {{ formatMemory(gpuInfo.total_memory) }}</div>
        <div>已用: {{ formatMemory(gpuInfo.used_memory) }}</div>
        <div>空闲: {{ formatMemory(gpuInfo.free_memory) }}</div>
        <div>可同时启动任务数: {{ gpuInfo.max_concurrent_tasks || 0 }}</div>
      </div>
    </div>

    <div class="tasks-container" v-if="tasks.length > 0">
      <div class="tasks-header">
        <h3>推理任务列表(启动推理后需等待服务完全就绪，状态变为"<span class="status-ready">准备就绪</span>"后才能进行聊天或使用API)</h3>
        <button @click="refreshTasks" class="btn btn-secondary btn-sm">
          <span class="material-icons">refresh</span>
          刷新
        </button>
      </div>
      
      <div class="tasks-grid">
        <div v-for="task in tasks" :key="task.id" class="task-card">
          <div class="task-header" :class="{'running': task.status === 'RUNNING' || isReady(task)}">
            <h3 class="task-name">{{ task.name }}</h3>
            <div class="task-status" :class="getStatusClass(task)" :title="getStatusTooltip(task)">
              {{ getStatusText(task) }}
            </div>
          </div>
          
          <div class="task-content">
            <div class="task-info">
              <p><strong>ID:</strong> {{ task.id }}</p>
              <p><strong>模型:</strong> {{ getModelName(task.model_id) }}</p>
              <p><strong>创建时间:</strong> {{ formatDateTime(task.created_at) }}</p>
              <p v-if="task.started_at"><strong>启动时间:</strong> {{ formatDateTime(task.started_at) }}</p>
              <p v-if="task.gpu_memory"><strong>显存占用:</strong> {{ formatMemory(task.gpu_memory) }}</p>
              <p><strong>共享状态:</strong> 
                <span class="share-status" :class="{'share-enabled': task.share_enabled}">
                  {{ task.share_enabled ? '已共享' : '未共享' }}
                </span>
              </p>
              
              <!-- 添加健康状态指示器 -->
              <p v-if="task.status === 'RUNNING'" class="health-status">
                <strong>服务状态:</strong>
                <span class="health-indicator" :class="{'healthy': isReady(task), 'unhealthy': !isReady(task)}">
                  {{ isReady(task) ? '可用' : '加载中' }}
                </span>
              </p>
            </div>
            
            <div class="task-error" v-if="task.error_message">
              <p class="error-message">{{ task.error_message }}</p>
            </div>
            
            <div class="task-actions">
              <router-link :to="`/inference/${task.id}`" class="btn btn-info btn-sm">
                <span class="material-icons">info</span>
                详情
              </router-link>
              
              <button @click="startTask(task.id)" class="btn btn-success btn-sm" 
                     v-if="task.status !== 'RUNNING' && task.status !== 'CREATING'">
                <span class="material-icons">play_arrow</span>
                启动
              </button>
              
              <button @click="stopTask(task.id)" class="btn btn-warning btn-sm" 
                     v-if="task.status === 'RUNNING'">
                <span class="material-icons">stop</span>
                停止
              </button>
              
              <button @click="checkServiceHealth(task.id)" class="btn btn-secondary btn-sm"
                     v-if="task.status === 'RUNNING' && !isReady(task)">
                <span class="material-icons">health_and_safety</span>
                检查服务
              </button>
              
              <router-link :to="`/chat/${task.id}`" class="btn btn-primary btn-sm" 
                          v-if="task.status === 'RUNNING' && isReady(task)">
                <span class="material-icons">chat</span>
                聊天
              </router-link>
              
              <button class="btn btn-primary btn-sm" disabled
                     v-if="task.status === 'RUNNING' && !isReady(task)">
                <span class="material-icons">hourglass_empty</span>
                准备中...
              </button>
              
              <button @click="confirmDelete(task.id)" class="btn btn-danger btn-sm" 
                     v-if="task.status !== 'RUNNING' && task.status !== 'CREATING'">
                <span class="material-icons">delete</span>
                删除
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <div class="empty-state" v-else>
      <div class="empty-icon">
        <span class="material-icons">sentiment_dissatisfied</span>
      </div>
      <h3>没有推理任务</h3>
      <p>点击"新建推理任务"按钮创建您的第一个推理任务</p>
    </div>

    <!-- 创建任务对话框 -->
    <div class="modal" v-if="showCreateModal">
      <div class="modal-content">
        <div class="modal-header">
          <h3>创建推理任务</h3>
          <button @click="showCreateModal = false" class="btn-close">
            <span class="material-icons">close</span>
          </button>
        </div>
        
        <div class="modal-body">
          <form @submit.prevent="createTask">
            <div class="form-group">
              <label for="taskName">任务名称</label>
              <input type="text" id="taskName" v-model="newTask.name" required>
            </div>
            
            <div class="form-group">
              <label for="modelId">选择模型</label>
              <select id="modelId" v-model="newTask.model_id" required>
                <option value="" disabled selected>选择一个模型</option>
                <option v-for="model in models" :key="model.id" :value="model.id">
                  {{ model.name }}
                </option>
              </select>
            </div>

            <div class="form-group">
              <label for="tensorParallelSize">Tensor并行大小</label>
              <input type="number" id="tensorParallelSize" v-model="newTask.tensor_parallel_size" min="1" max="8">
              <small>使用多少GPU进行张量并行（默认为1）</small>
            </div>
            
            <div class="form-group">
              <label for="maxModelLen">最大模型长度</label>
              <input type="number" id="maxModelLen" v-model="newTask.max_model_len" min="256" max="32768">
              <small>模型最大序列长度（默认为4096）</small>
            </div>
            
            <div class="form-group">
              <label for="quantization">量化方法</label>
              <select id="quantization" v-model="newTask.quantization">
                <option value="">不使用量化</option>
                <option value="awq">AWQ</option>
                <option value="gptq">GPTQ</option>
              </select>
              <small>使用量化可减少显存占用</small>
            </div>
            
            <div class="form-group">
              <label>分享设置</label>
              <div class="sharing-options">
                <div class="checkbox-group">
                  <input type="checkbox" id="shareEnabled" v-model="newTask.share_enabled">
                  <label for="shareEnabled">启用共享</label>
                  <small>启用后，其他用户可以通过共享链接访问此推理任务</small>
                </div>
                
                <div class="input-group" v-if="newTask.share_enabled">
                  <label for="displayName">显示名称</label>
                  <input type="text" id="displayName" v-model="newTask.display_name" placeholder="公开显示的名称（可选）">
                  <small>不填写将使用任务名称</small>
                </div>
              </div>
            </div>
            
            <div class="form-group">
              <label>推理参数</label>
              <div class="inference-params">
                <div class="param-group">
                  <label for="maxTokens">最大输出Token</label>
                  <input type="number" id="maxTokens" v-model="newTask.max_tokens" min="1" max="4096">
                </div>
                
                <div class="param-group">
                  <label for="temperature">温度</label>
                  <input type="number" id="temperature" v-model="newTask.temperature" min="0" max="2" step="0.1">
                </div>
                
                <div class="param-group">
                  <label for="topP">Top P</label>
                  <input type="number" id="topP" v-model="newTask.top_p" min="0" max="1" step="0.1">
                </div>
                
                <div class="param-group">
                  <label for="topK">Top K</label>
                  <input type="number" id="topK" v-model="newTask.top_k" min="1" max="100">
                </div>
                
                <div class="param-group">
                  <label for="repetitionPenalty">重复惩罚</label>
                  <input type="number" id="repetitionPenalty" v-model="newTask.repetition_penalty" min="1" max="2" step="0.1">
                </div>
              </div>
            </div>
            
            <div class="modal-footer">
              <button type="button" @click="showCreateModal = false" class="btn btn-secondary">取消</button>
              <button type="submit" class="btn btn-primary" :disabled="isCreating">
                {{ isCreating ? '创建中...' : '创建任务' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
    
    <!-- 删除确认对话框 -->
    <div class="modal" v-if="showDeleteModal">
      <div class="modal-content">
        <div class="modal-header">
          <h3>确认删除</h3>
          <button @click="showDeleteModal = false" class="btn-close">
            <span class="material-icons">close</span>
          </button>
        </div>
        
        <div class="modal-body">
          <p>您确定要删除此推理任务吗？此操作无法撤销。</p>
          
          <div class="modal-footer">
            <button @click="showDeleteModal = false" class="btn btn-secondary">取消</button>
            <button @click="deleteTask" class="btn btn-danger">确认删除</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { apiClient, inference } from '../api/client'
import { useToast } from '../composables/toast'

export default {
  name: 'InferencePage',
  setup() {
    const { showToast } = useToast()
    
    // 数据
    const tasks = ref([])
    const models = ref([])
    const gpuInfo = ref(null)
    const isLoading = ref(false)
    const isCreating = ref(false)
    const showCreateModal = ref(false)
    const showDeleteModal = ref(false)
    const taskToDelete = ref(null)
    const taskHealthStatus = ref({}) // 保存任务健康状态
    
    // 新任务表单
    const newTask = reactive({
      name: '',
      model_id: '',
      tensor_parallel_size: 1,
      max_model_len: 4096,
      quantization: '',
      max_tokens: 2048,
      temperature: 0.7,
      top_p: 0.9,
      top_k: 50,
      repetition_penalty: 1.1,
      share_enabled: false,
      display_name: ''
    })
    
    // 刷新定时器
    let refreshTimer = null
    
    // 加载任务列表
    const loadTasks = async () => {
      try {
        isLoading.value = true
        const response = await inference.getTasks()
        tasks.value = response.data
      } catch (error) {
        console.error('加载推理任务失败:', error)
        showToast('加载推理任务失败', 'error')
      } finally {
        isLoading.value = false
      }
    }
    
    // 加载可用模型
    const loadModels = async () => {
      try {
        const response = await apiClient.get('/api/resources', {
          params: { resource_type: 'MODEL', status: 'COMPLETED' }
        })
        models.value = response.data
      } catch (error) {
        console.error('加载模型列表失败:', error)
        showToast('加载模型列表失败', 'error')
      }
    }
    
    // 加载GPU信息
    const loadGpuInfo = async () => {
      try {
        const response = await inference.getGpuStatus()
        gpuInfo.value = response.data
      } catch (error) {
        console.error('加载GPU信息失败:', error)
      }
    }
    
    // 检查任务是否准备就绪
    const checkTaskHealth = async (taskId) => {
      if (!taskId) return false
      
      try {
        const response = await inference.getTaskStatus(taskId)
        console.log("健康检查响应:", response.data)
        
        // 根据后端API返回的格式判断服务是否就绪
        // 后端API返回的是包含api_available字段的对象
        const isHealthy = response.data?.api_available === true
        
        // 更新任务健康状态
        taskHealthStatus.value[taskId] = isHealthy
        return isHealthy
      } catch (error) {
        console.error(`检查任务 ${taskId} 健康状态失败:`, error)
        taskHealthStatus.value[taskId] = false
        return false
      }
    }
    
    // 检查所有运行中任务的健康状态
    const checkAllTasksHealth = async () => {
      const runningTasks = tasks.value.filter(t => t.status === 'RUNNING')
      
      for (const task of runningTasks) {
        await checkTaskHealth(task.id)
      }
    }
    
    // 修改刷新任务，增加健康检查
    const refreshTasks = async () => {
      await Promise.all([
        loadTasks(),
        loadGpuInfo()
      ])
      
      // 在加载任务后，检查所有运行中任务的健康状态
      await checkAllTasksHealth()
    }
    
    // 打开创建对话框
    const openCreateModal = () => {
      // 重置表单
      Object.assign(newTask, {
        name: '',
        model_id: '',
        tensor_parallel_size: 1,
        max_model_len: 4096,
        quantization: '',
        max_tokens: 2048,
        temperature: 0.7,
        top_p: 0.9,
        top_k: 50,
        repetition_penalty: 1.1,
        share_enabled: false,
        display_name: ''
      })
      showCreateModal.value = true
    }
    
    // 创建任务
    const createTask = async () => {
      try {
        isCreating.value = true
        const response = await inference.createTask(newTask)
        showToast('推理任务创建成功', 'success')
        showCreateModal.value = false
        await refreshTasks()
      } catch (error) {
        console.error('创建推理任务失败:', error)
        showToast('创建推理任务失败: ' + (error.response?.data?.detail || error.message), 'error')
      } finally {
        isCreating.value = false
      }
    }
    
    // 启动任务
    const startTask = async (taskId) => {
      try {
        showToast('正在启动推理任务...', 'info')
        await inference.startTask(taskId)
        showToast('推理任务启动成功', 'success')
        await refreshTasks()
      } catch (error) {
        console.error('启动推理任务失败:', error)
        showToast('启动推理任务失败: ' + (error.response?.data?.detail || error.message), 'error')
      }
    }
    
    // 停止任务
    const stopTask = async (taskId) => {
      try {
        showToast('正在停止推理任务...', 'info')
        await inference.stopTask(taskId)
        showToast('推理任务已停止', 'success')
        await refreshTasks()
      } catch (error) {
        console.error('停止推理任务失败:', error)
        showToast('停止推理任务失败: ' + (error.response?.data?.detail || error.message), 'error')
      }
    }
    
    // 检查服务健康状态
    const checkServiceHealth = async (taskId) => {
      try {
        showToast('正在检查服务状态...', 'info')
        const response = await inference.getTaskStatus(taskId)
        console.log("服务状态检查结果:", response.data)
        
        const isHealthy = response.data?.api_available === true
        const processRunning = response.data?.process_running === true
        
        if (isHealthy) {
          showToast('服务已就绪，可以开始使用', 'success')
        } else if (processRunning) {
          showToast('服务进程正在运行，但API尚未就绪，请稍后再试', 'warning')
        } else {
          showToast('服务未就绪，进程可能已终止', 'error')
        }
        
        // 刷新任务列表以更新状态
        await refreshTasks()
      } catch (error) {
        showToast('检查服务状态失败: ' + (error.response?.data?.detail || error.message), 'error')
      }
    }
    
    // 打开删除确认对话框
    const confirmDelete = (taskId) => {
      taskToDelete.value = taskId
      showDeleteModal.value = true
    }
    
    // 删除任务
    const deleteTask = async () => {
      if (!taskToDelete.value) return
      
      try {
        await inference.deleteTask(taskToDelete.value)
        showToast('推理任务已删除', 'success')
        showDeleteModal.value = false
        await refreshTasks()
      } catch (error) {
        console.error('删除推理任务失败:', error)
        showToast('删除推理任务失败: ' + (error.response?.data?.detail || error.message), 'error')
      } finally {
        taskToDelete.value = null
      }
    }
    
    // 获取模型名称
    const getModelName = (modelId) => {
      const model = models.value.find(m => m.id === modelId)
      return model ? model.name : `模型 #${modelId}`
    }
    
    // 格式化内存大小
    const formatMemory = (memory) => {
      if (memory === undefined || memory === null) return '未知'
      return `${memory.toFixed(1)} GB`
    }
    
    // 格式化时间
    const formatDateTime = (dateTime) => {
      if (!dateTime) return '未知'
      
      // 处理ISO字符串
      const date = typeof dateTime === 'string' 
        ? new Date(dateTime) 
        : dateTime
      
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      })
    }
    
    // 获取状态文本
    const getStatusText = (task) => {
      // 首先检查任务的API是否可用
      if (task.status === 'RUNNING' && isReady(task)) {
        return '准备就绪'
      }
      
      // 如果进程在运行但API未就绪
      if (task.status === 'RUNNING' && !isReady(task)) {
        return '正在加载模型...'
      }
      
      const statusMap = {
        'CREATING': '创建中',
        'RUNNING': '已启动',
        'STOPPED': '已停止',
        'FAILED': '失败'
      }
      return statusMap[task.status] || task.status
    }
    
    // 添加状态提示，解释当前状态
    const getStatusTooltip = (task) => {
      if (task.status === 'RUNNING' && isReady(task)) {
        return '服务已完全就绪，可以开始聊天或使用API'
      }
      
      if (task.status === 'RUNNING' && !isReady(task)) {
        return '模型正在加载中，请等待模型完全加载后再开始使用（可能需要1-2分钟）'
      }
      
      if (task.status === 'FAILED') {
        return task.error_message || '启动失败，请查看详情了解更多信息'
      }
      
      if (task.status === 'STOPPED') {
        return '服务已停止，需要重新启动才能使用'
      }
      
      return '等待启动'
    }
    
    // 修改isReady函数，使用健康检查结果
    const isReady = (task) => {
      if (task.status !== 'RUNNING') return false
      
      // 使用健康检查结果判断任务是否准备就绪
      return !!taskHealthStatus.value[task.id]
    }
    
    const getStatusClass = (task) => {
      if (task.status === 'RUNNING' && isReady(task)) {
        return 'ready'
      }
      
      if (task.status === 'RUNNING' && !isReady(task)) {
        return 'loading'
      }
      
      return task.status.toLowerCase()
    }
    
    // 生命周期钩子
    onMounted(async () => {
      await Promise.all([
        loadTasks(),
        loadModels(),
        loadGpuInfo()
      ])
      
      // 执行一次健康检查
      await checkAllTasksHealth()
      
      // 设置定时刷新
      refreshTimer = setInterval(refreshTasks, 10000)
    })
    
    onUnmounted(() => {
      // 清除定时器
      if (refreshTimer) {
        clearInterval(refreshTimer)
      }
    })
    
    return {
      tasks,
      models,
      gpuInfo,
      isLoading,
      isCreating,
      showCreateModal,
      showDeleteModal,
      newTask,
      openCreateModal,
      createTask,
      refreshTasks,
      startTask,
      stopTask,
      confirmDelete,
      deleteTask,
      getModelName,
      formatMemory,
      formatDateTime,
      getStatusText,
      getStatusTooltip,
      isReady,
      getStatusClass,
      taskHealthStatus,
      checkServiceHealth
    }
  }
}
</script>

<style scoped>
.inference-page {
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.gpu-status {
  background-color: var(--surface-color);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.gpu-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.gpu-card {
  background-color: var(--surface-variant-color);
  border-radius: 6px;
  padding: 12px;
}

.gpu-name {
  font-weight: bold;
  margin-bottom: 8px;
}

.progress {
  height: 8px;
  background-color: var(--surface-color);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 4px;
}

.progress-bar {
  height: 100%;
  background-color: var(--primary);
  border-radius: 4px;
}

.memory-text {
  font-size: 0.9em;
  color: var(--text-secondary);
}

.gpu-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--divider-color);
}

.tasks-container {
  margin-top: 24px;
}

.tasks-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.tasks-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 16px;
}

.task-card {
  background-color: var(--surface-color);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition: transform 0.2s, box-shadow 0.2s;
}

.task-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.task-header {
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: var(--surface-variant-color);
  border-bottom: 1px solid var(--divider-color);
}

.task-header.running {
  background-color: var(--primary);
  color: var(--on-primary);
}

.task-name {
  font-size: 18px;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-status {
  font-size: 0.9em;
  padding: 4px 8px;
  border-radius: 4px;
  background-color: var(--surface-color);
}

.task-status.running {
  background-color: #FFC107;
  color: black;
}

.task-status.ready {
  background-color: #4CAF50;
  color: white;
  animation: pulse-green 2s infinite;
}

.status-ready {
  color: #4CAF50;
  font-weight: bold;
}

@keyframes pulse-green {
  0% {
    box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.7);
  }
  70% {
    box-shadow: 0 0 0 5px rgba(76, 175, 80, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(76, 175, 80, 0);
  }
}

.task-status.creating {
  background-color: #2196F3;
  color: white;
}

.task-status.stopped {
  background-color: #ff9e80;
  color: white;
}

.task-status.failed {
  background-color: #F44336;
  color: white;
}

.task-status.loading {
  background-color: #FFC107;
  color: black;
  animation: pulse-loading 1.5s infinite;
}

@keyframes pulse-loading {
  0% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
  100% {
    opacity: 1;
  }
}

.task-content {
  padding: 16px;
}

.task-info {
  margin-bottom: 16px;
}

.task-info p {
  margin: 8px 0;
  color: var(--text-primary);
}

.task-error {
  margin-bottom: 16px;
  padding: 8px;
  background-color: #FFEBEE;
  border-radius: 4px;
  border-left: 3px solid #F44336;
}

.error-message {
  color: #D32F2F;
  margin: 0;
  font-size: 0.9em;
}

.task-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.empty-state {
  text-align: center;
  padding: 48px 0;
  background-color: var(--surface-color);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.empty-icon {
  margin-bottom: 16px;
}

.empty-icon .material-icons {
  font-size: 48px;
  color: var(--text-secondary);
}

.empty-state h3 {
  margin-bottom: 8px;
  color: var(--text-primary);
}

.empty-state p {
  color: var(--text-secondary);
}

/* 模态框样式 */
.modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background-color: var(--surface-color);
  border-radius: 8px;
  width: 90%;
  max-width: 600px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--divider-color);
}

.modal-header h3 {
  margin: 0;
}

.btn-close {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
}

.modal-body {
  padding: 16px;
}

.modal-footer {
  padding: 16px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  border-top: 1px solid var(--divider-color);
  margin-top: 16px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--divider-color);
  border-radius: 4px;
  background-color: var(--background-color);
  color: var(--text-primary);
}

.form-group small {
  display: block;
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 0.9em;
}

.inference-params {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.param-group {
  margin-bottom: 8px;
}

.param-group label {
  font-size: 0.9em;
  margin-bottom: 4px;
}

/* 分享设置样式 */
.sharing-options {
  margin-top: 8px;
}

.checkbox-group {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.checkbox-group input[type="checkbox"] {
  width: auto;
  margin-right: 8px;
}

.checkbox-group label {
  display: inline;
  margin-right: 8px;
  font-weight: normal;
}

.checkbox-group small {
  margin-top: 0;
  margin-left: 4px;
}

.input-group {
  margin-top: 12px;
}

.input-group label {
  margin-bottom: 4px;
}

/* 按钮样式 */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s, transform 0.1s;
  border: none;
  gap: 8px;
}

.btn:hover {
  transform: translateY(-1px);
}

.btn:active {
  transform: translateY(0);
}

.btn-sm {
  padding: 4px 8px;
  font-size: 12px;
}

.btn-primary {
  background-color: #ff9e80;
  color: white;
  border: 1px solid transparent;
}

.btn-primary:hover {
  background-color: #ff9e80;
  filter: brightness(1.1);
}

[data-theme="dark"] .btn-primary {
  background-color: #ff9e80;
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.btn-secondary {
  background-color: var(--surface-variant-color, #f5f5f5);
  color: var(--on-surface-variant, #333);
  border: 1px solid var(--divider-color, #ddd);
}

.btn-secondary:hover {
  background-color: var(--surface-variant-color-hover, #e0e0e0);
}

[data-theme="dark"] .btn-secondary {
  background-color: var(--surface-variant-color, #3a3a3a);
  color: var(--on-surface-variant, #eee);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.btn-outline {
  background-color: transparent;
  color: var(--primary, #1976d2);
  border: 1px solid var(--primary, #1976d2);
}

.btn-outline:hover {
  background-color: rgba(var(--primary-rgb, '25, 118, 210'), 0.05);
}

[data-theme="dark"] .btn-outline {
  color: var(--primary, #1976d2);
  border: 1px solid var(--primary, #1976d2);
}

.btn-info {
  background-color: #2196F3;
  color: white;
}

[data-theme="dark"] .btn-info {
  background-color: #2196F3;
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.btn-success {
  background-color: #4CAF50;
  color: white;
}

[data-theme="dark"] .btn-success {
  background-color: #4CAF50;
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.btn-warning {
  background-color: #ff9e80;
  color: white;
}

[data-theme="dark"] .btn-warning {
  background-color: #ff9e80;
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.btn-danger {
  background-color: #F44336;
  color: white;
}

[data-theme="dark"] .btn-danger {
  background-color: #F44336;
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.btn[disabled] {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 响应式调整 */
@media (max-width: 768px) {
  .tasks-grid {
    grid-template-columns: 1fr;
  }
  
  .inference-params {
    grid-template-columns: 1fr;
  }
  
  .gpu-cards {
    grid-template-columns: 1fr;
  }
}

/* 添加健康状态指示器样式 */
.health-status {
  margin-top: 12px;
}

.health-indicator {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: bold;
}

.health-indicator.healthy {
  background-color: #4CAF50;
  color: white;
}

.health-indicator.unhealthy {
  background-color: #FFC107;
  color: black;
}

/* 共享状态样式 */
.share-status {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: bold;
  background-color: #e0e0e0;
  color: #666;
}

.share-status.share-enabled {
  background-color: #4CAF50;
  color: white;
}
</style> 