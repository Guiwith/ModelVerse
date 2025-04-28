<template>
  <div class="training-detail-page">
    <div v-if="loading" class="loading-container">
      <div class="loader"></div>
      <p>加载训练任务详情...</p>
    </div>

    <div v-else-if="error" class="error-message">
      <span class="material-icons">error</span>
      <p>{{ error }}</p>
      <button class="btn btn-outline" @click="loadTask">重试</button>
      <router-link to="/training" class="btn btn-outline">返回训练任务列表</router-link>
    </div>

    <template v-else>
      <div class="page-header">
        <div class="header-left">
          <router-link to="/training" class="btn-back">
            <span class="material-icons">arrow_back</span>
          </router-link>
          <div>
            <h1>{{ task.name }}</h1>
            <p class="subtitle">任务ID: {{ task.id }}</p>
          </div>
        </div>
        <div class="header-right">
          <span class="task-status" :class="getStatusClass(task.status)">
            {{ getStatusText(task.status) }}
          </span>
          <button 
            v-if="task.status === 'PENDING'" 
            class="btn btn-success" 
            @click="startTask">
            <span class="material-icons">play_arrow</span> 开始训练
          </button>
          <button 
            v-if="task.status === 'RUNNING'" 
            class="btn btn-danger" 
            @click="stopTask">
            <span class="material-icons">stop</span> 停止训练
          </button>
          <button
            v-if="task.status !== 'RUNNING'"
            class="btn btn-danger"
            @click="deleteTask">
            <span class="material-icons">delete</span> 删除任务
          </button>
        </div>
      </div>

      <div class="task-container">
        <div class="task-info-panel">
          <div class="panel-card">
            <h2>训练基本信息</h2>
            <div class="info-grid">
              <div class="info-item">
                <span class="info-label">状态:</span>
                <span class="info-value status" :class="getStatusClass(task.status)">
                  {{ getStatusText(task.status) }}
                </span>
              </div>
              <div class="info-item">
                <span class="info-label">基础模型:</span>
                <span class="info-value">{{ getResourceName(task.base_model_id) }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">数据集:</span>
                <span class="info-value">{{ getResourceName(task.dataset_id) }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">创建时间:</span>
                <span class="info-value">{{ formatDate(task.created_at) }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">开始时间:</span>
                <span class="info-value">{{ task.started_at ? formatDate(task.started_at) : '尚未开始' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">完成时间:</span>
                <span class="info-value">{{ task.completed_at ? formatDate(task.completed_at) : '尚未完成' }}</span>
              </div>
            </div>
          </div>

          <div class="panel-card">
            <h2>训练配置</h2>
            <div class="config-section">
              <h3>模型配置</h3>
              <div class="config-items" v-if="task.config_path">
                <div class="config-item" v-for="(value, key) in modelConfig" :key="key">
                  <span class="config-label">{{ formatConfigKey(key) }}:</span>
                  <span class="config-value">{{ formatConfigValue(value) }}</span>
                </div>
              </div>
            </div>
            <div class="config-section">
              <h3>训练参数</h3>
              <div class="config-items" v-if="task.config_path">
                <div class="config-item" v-for="(value, key) in trainingConfig" :key="key">
                  <span class="config-label">{{ formatConfigKey(key) }}:</span>
                  <span class="config-value">{{ formatConfigValue(value) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="logs-panel">
          <div class="panel-card">
            <div class="logs-header">
              <h2>训练日志</h2>
              <div class="logs-actions">
                <button class="btn btn-outline" @click="clearLogs">
                  <span class="material-icons">clear_all</span> 清除
                </button>
                <button class="btn btn-outline" :class="{ active: autoScroll }" @click="toggleAutoScroll">
                  <span class="material-icons">vertical_align_bottom</span> 自动滚动
                </button>
              </div>
            </div>
            
            <div v-if="task.status === 'RUNNING'" class="progress-bar">
              <div class="progress-fill" :style="{ width: `${task.progress * 100}%` }"></div>
              <span class="progress-text">{{ Math.round(task.progress * 100) }}%</span>
            </div>

            <div class="logs-container" ref="logsContainer">
              <div v-if="logs.length === 0" class="empty-logs">
                <span class="material-icons">description</span>
                <p>暂无日志数据</p>
              </div>
              <div v-else class="logs-content">
                <div v-for="(log, index) in logs" :key="index" :class="['log-entry', `log-${log.level.toLowerCase()}`]">
                  <span class="log-time">{{ formatLogTime(log.timestamp) }}</span>
                  <span class="log-level">{{ log.level }}</span>
                  <span class="log-content">{{ log.content }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
// @ts-ignore
import { apiClient, training } from '../api/client'


interface LogEntry {
  timestamp: string;
  level: string;
  content: string;
}

interface TrainingTask {
  id: string;
  name: string;
  status: string;
  base_model_id: string;
  dataset_id: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  progress?: number;
  config_path?: string;
  config_params?: {
    model?: Record<string, any>;
    training?: Record<string, any>;
  };
}

interface Resource {
  id: string;
  name: string;
}

export default {
  name: 'TrainingDetail',
  setup() {
    const route = useRoute()
    const router = useRouter()
    const taskId = computed(() => route.params.id as string)
    
    const task = ref<TrainingTask>({} as TrainingTask)
    const logs = ref<LogEntry[]>([])
    const loading = ref(true)
    const error = ref<string | null>(null)
    const socket = ref<WebSocket | null>(null)
    const autoScroll = ref(true)
    const logsContainer = ref<HTMLElement | null>(null)
    const resources = ref<Record<string, string>>({}) // 保存资源ID到名称的映射
    
    // 从任务配置中提取的模型配置和训练配置
    const modelConfig = computed(() => {
      if (!task.value.config_params) return {}
      return task.value.config_params.model || {}
    })
    
    const trainingConfig = computed(() => {
      if (!task.value.config_params) return {}
      return task.value.config_params.training || {}
    })
    
    // 加载任务详情
    const loadTask = async () => {
      loading.value = true
      error.value = null
      
      try {
        const response = await training.getTaskById(taskId.value)
        task.value = response.data as TrainingTask
        
        // 清空现有日志
        logs.value = []
        
        // 如果任务正在运行，建立WebSocket连接接收实时日志
        if (task.value.status === 'RUNNING' || task.value.status === 'PENDING') {
          connectWebSocket()
        } else {
          // 对于非运行状态的任务，加载最新日志
          await loadLogs()
        }
      } catch (err: any) {
        console.error('加载训练任务详情失败:', err)
        error.value = '无法加载训练任务详情，请检查任务ID是否存在'
      } finally {
        loading.value = false
      }
    }
    
    // 加载任务日志
    const loadLogs = async () => {
      try {
        const response = await training.getLogs(taskId.value)
        logs.value = response.data as LogEntry[]
        
        // 如果启用了自动滚动，滚动到最新日志
        if (autoScroll.value) {
          await nextTick()
          scrollToBottom()
        }
      } catch (err) {
        console.error('加载训练日志失败:', err)
      }
    }
    
    // 加载资源信息（模型和数据集名称）
    const loadResourcesInfo = async () => {
      try {
        // 加载模型信息
        const modelsResponse = await training.getAvailableModels()
        
        // 加载数据集信息
        const datasetsResponse = await training.getAvailableDatasets()
        
        // 合并资源信息
        const modelResources = modelsResponse.data || []
        const datasetResources = datasetsResponse.data || []
        
        // 将资源数据添加到映射中
        const allResources = [...(modelResources as Resource[]), ...(datasetResources as Resource[])]
        allResources.forEach(resource => {
          if (resource && resource.id) {
            resources.value[resource.id] = resource.name
          }
        })
      } catch (err) {
        console.error('加载资源信息失败:', err)
      }
    }
    
    // 连接WebSocket获取实时日志
    const connectWebSocket = () => {
      if (socket.value) {
        socket.value.close()
      }
      
      // 清空现有日志，确保只显示新的日志
      logs.value = []
      
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.host
      const wsUrl = `${protocol}//${host}/ws/training/${taskId.value}`
      
      console.log('连接WebSocket:', wsUrl)
      
      socket.value = new WebSocket(wsUrl)
      
      socket.value.onopen = () => {
        console.log('WebSocket连接已建立')
      }
      
      socket.value.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          console.log('WebSocket收到消息:', data)
          
          if (data.content && data.timestamp && data.level) {
            // 直接处理日志消息格式
            const logEntry = {
              timestamp: data.timestamp,
              level: data.level,
              content: data.content
            }
            
            logs.value.push(logEntry)
            console.log('添加日志:', logEntry)
            
            // 如果启用了自动滚动，滚动到最新日志
            if (autoScroll.value) {
              nextTick(scrollToBottom)
            }
            
            // 确保UI更新
            nextTick(() => {
              if (logsContainer.value) {
                // 强制触发DOM更新
                logsContainer.value.style.display = 'none'
                setTimeout(() => {
                  if (logsContainer.value) {
                    logsContainer.value.style.display = ''
                    scrollToBottom()
                  }
                }, 0)
              }
            })
          } else if (data.type === 'log') {
            // 兼容旧格式
            logs.value.push(data.log)
            
            // 如果启用了自动滚动，滚动到最新日志
            if (autoScroll.value) {
              nextTick(scrollToBottom)
            }
          } else if (data.type === 'progress') {
            // 更新训练进度
            task.value.progress = data.progress
          } else if (data.type === 'status') {
            // 更新任务状态
            task.value.status = data.status
            
            // 如果任务已完成或停止，关闭WebSocket连接
            if (['COMPLETED', 'FAILED', 'STOPPED'].includes(data.status)) {
              socket.value?.close()
              
              // 重新加载任务信息以获取最新状态
              loadTask()
            }
          } else {
            // 处理其他未知格式
            console.log('收到未知格式WebSocket消息:', data)
          }
        } catch (err) {
          console.error('处理WebSocket消息失败:', err, event.data)
          
          // 尝试作为纯文本添加
          const logEntry = {
            timestamp: new Date().toISOString(),
            level: 'INFO',
            content: event.data
          }
          
          logs.value.push(logEntry)
          
          // 如果启用了自动滚动，滚动到最新日志
          if (autoScroll.value) {
            nextTick(scrollToBottom)
          }
        }
      }
      
      socket.value.onerror = (error) => {
        console.error('WebSocket错误:', error)
      }
      
      socket.value.onclose = () => {
        console.log('WebSocket连接已关闭')
      }
    }
    
    // 滚动到日志底部
    const scrollToBottom = () => {
      if (logsContainer.value) {
        logsContainer.value.scrollTop = logsContainer.value.scrollHeight
      }
    }
    
    // 切换自动滚动
    const toggleAutoScroll = () => {
      autoScroll.value = !autoScroll.value
      if (autoScroll.value) {
        scrollToBottom()
      }
    }
    
    // 清除日志
    const clearLogs = () => {
      logs.value = []
    }
    
    // 开始训练任务
    const startTask = async () => {
      try {
        // 先清除前端日志显示
        logs.value = []
        
        // 停止现有WebSocket连接
        if (socket.value) {
          socket.value.close()
        }
        
        // 开始训练
        await training.startTask(taskId.value)
        
        // 短暂延迟，让后端有时间清理日志
        await new Promise(resolve => setTimeout(resolve, 1000))
        
        // 更新任务状态并建立新的WebSocket连接
        await loadTask()
      } catch (err: any) {
        console.error('开始训练任务失败:', err)
        alert(`开始训练任务失败: ${err.response?.data?.detail || '未知错误'}`)
      }
    }
    
    // 停止训练任务
    const stopTask = async () => {
      if (confirm('确定要停止此训练任务吗？')) {
        try {
          await training.stopTask(taskId.value)
          
          // 更新任务状态
          await loadTask()
        } catch (err: any) {
          console.error('停止训练任务失败:', err)
          alert(`停止训练任务失败: ${err.response?.data?.detail || '未知错误'}`)
        }
      }
    }
    
    // 删除训练任务
    const deleteTask = async () => {
      if (confirm('确定要删除此训练任务吗？此操作不可恢复。')) {
        try {
          await training.deleteTask(taskId.value)
          // 删除成功后返回到任务列表页
          router.push('/training')
        } catch (err: any) {
          console.error('删除训练任务失败:', err)
          alert(`删除训练任务失败: ${err.response?.data?.detail || '未知错误'}`)
        }
      }
    }
    
    // 格式化配置键名
    const formatConfigKey = (key: string) => {
      return key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')
    }
    
    // 格式化配置值
    const formatConfigValue = (value: any) => {
      if (value === null || value === undefined) return '未设置'
      if (typeof value === 'boolean') return value ? '是' : '否'
      if (typeof value === 'object') return JSON.stringify(value)
      return value.toString()
    }
    
    // 获取资源名称
    const getResourceName = (resourceId: string) => {
      return resources.value[resourceId] || `资源#${resourceId}`
    }
    
    // 格式化日期
    const formatDate = (dateString: string) => {
      if (!dateString) return ''
      const date = new Date(dateString)
      return date.toLocaleString()
    }
    
    // 格式化日志时间
    const formatLogTime = (timestamp: string) => {
      const date = new Date(timestamp)
      return date.toLocaleTimeString()
    }
    
    // 获取状态文本
    const getStatusText = (status: string) => {
      const statusMap: Record<string, string> = {
        'PENDING': '等待中',
        'RUNNING': '运行中',
        'COMPLETED': '已完成',
        'FAILED': '失败',
        'STOPPED': '已停止'
      }
      return statusMap[status] || status
    }
    
    // 获取状态样式类
    const getStatusClass = (status: string) => {
      const classMap: Record<string, string> = {
        'PENDING': 'status-pending',
        'RUNNING': 'status-running',
        'COMPLETED': 'status-completed',
        'FAILED': 'status-failed',
        'STOPPED': 'status-stopped'
      }
      return classMap[status] || ''
    }
    
    // 添加周期性检查，确保日志显示是最新的
    let intervalId: number
    
    const checkForUpdates = async () => {
      if (task.value.status === 'RUNNING') {
        // 如果任务正在运行但没有日志，尝试获取最新日志
        if (logs.value.length === 0) {
          await loadLogs()
        }
        
        // 检查WebSocket是否仍然连接
        if (socket.value && socket.value.readyState !== WebSocket.OPEN) {
          console.log('WebSocket连接已关闭，重新连接...')
          connectWebSocket()
        }
      }
    }
    
    // 在加载任务时开始定期检查
    onMounted(() => {
      loadTask()
      loadResourcesInfo()
      
      // 每5秒检查一次更新
      intervalId = window.setInterval(checkForUpdates, 5000)
    })
    
    // 在组件卸载时清理
    onUnmounted(() => {
      if (socket.value) {
        socket.value.close()
      }
      
      // 清除检查间隔
      clearInterval(intervalId)
    })
    
    return {
      task,
      logs,
      loading,
      error,
      autoScroll,
      logsContainer,
      modelConfig,
      trainingConfig,
      loadTask,
      startTask,
      stopTask,
      deleteTask,
      clearLogs,
      toggleAutoScroll,
      getResourceName,
      formatDate,
      formatLogTime,
      formatConfigKey,
      formatConfigValue,
      getStatusText,
      getStatusClass
    }
  }
}
</script>

<style scoped>
.training-detail-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
}

.btn-back {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background-color: var(--bg-card-secondary);
  color: var(--text-primary);
  margin-right: 16px;
  transition: background-color 0.2s;
}

.btn-back:hover {
  background-color: var(--bg-hover);
}

.page-header h1 {
  font-size: 24px;
  margin: 0;
  margin-bottom: 4px;
}

.subtitle {
  color: var(--text-secondary);
  margin: 0;
}

.task-container {
  display: grid;
  grid-template-columns: 1fr 1.5fr;
  gap: 24px;
}

.panel-card {
  background-color: var(--bg-card);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 20px;
  margin-bottom: 24px;
}

.panel-card h2 {
  font-size: 20px;
  margin-top: 0;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-color);
}

/* 基本信息样式 */
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
}

.info-label {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.info-value {
  font-size: 16px;
}

.info-value.status {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 16px;
  font-size: 14px;
  font-weight: 500;
}

/* 配置信息样式 */
.config-section {
  margin-bottom: 20px;
}

.config-section h3 {
  font-size: 16px;
  margin-top: 0;
  margin-bottom: 12px;
  color: var(--text-secondary);
}

.config-items {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.config-item {
  display: flex;
  flex-direction: column;
}

.config-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 2px;
}

.config-value {
  font-size: 14px;
  word-break: break-word;
}

/* 日志面板样式 */
.logs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.logs-actions {
  display: flex;
  gap: 8px;
}

.logs-container {
  height: 400px;
  overflow-y: auto;
  background-color: var(--bg-card-secondary);
  border-radius: 4px;
  margin-top: 16px;
  padding: 12px;
  font-family: monospace;
  font-size: 13px;
  line-height: 1.5;
}

.empty-logs {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-tertiary);
}

.empty-logs .material-icons {
  font-size: 40px;
  margin-bottom: 12px;
}

.log-entry {
  margin-bottom: 4px;
  padding: 2px 0;
  display: grid;
  grid-template-columns: auto auto 1fr;
  gap: 8px;
  align-items: start;
}

.log-time {
  color: var(--text-tertiary);
}

.log-level {
  display: inline-block;
  min-width: 60px;
  text-align: center;
  padding: 0 4px;
  border-radius: 4px;
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
}

.log-info .log-level {
  background-color: #e3f2fd;
  color: #2196f3;
}

.log-warning .log-level {
  background-color: #fff8e1;
  color: #ff9800;
}

.log-error .log-level {
  background-color: #ffebee;
  color: #f44336;
}

.log-debug .log-level {
  background-color: #f5f5f5;
  color: #9e9e9e;
}

.log-content {
  white-space: pre-wrap;
  word-break: break-word;
}

/* 进度条样式 */
.progress-bar {
  height: 8px;
  background-color: var(--bg-card-secondary);
  border-radius: 4px;
  margin: 16px 0;
  position: relative;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background-color: #2196f3;
  transition: width 0.3s;
}

.progress-text {
  position: absolute;
  right: 0;
  top: -18px;
  font-size: 12px;
  color: #2196f3;
}

/* 状态标签样式 */
.task-status {
  display: inline-block;
  padding: 6px 12px;
  border-radius: 16px;
  font-size: 14px;
  font-weight: 500;
  margin-right: 12px;
}

.status-pending {
  background-color: #fff8e1;
  color: #ff9800;
}

.status-running {
  background-color: #e3f2fd;
  color: #2196f3;
}

.status-completed {
  background-color: #e8f5e9;
  color: #4caf50;
}

.status-failed {
  background-color: #ffebee;
  color: #f44336;
}

.status-stopped {
  background-color: #f5f5f5;
  color: #9e9e9e;
}

/* 按钮样式 */
.btn-outline.active {
  background-color: var(--primary-light);
  color: var(--primary);
}

/* 加载和错误样式 */
.loading-container, .error-message {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px 0;
  text-align: center;
}

.loader {
  border: 4px solid var(--bg-card-secondary);
  border-top: 4px solid var(--primary);
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.error-message {
  color: #f44336;
}

.error-message .material-icons {
  font-size: 48px;
  margin-bottom: 16px;
}

.error-message button, .error-message a {
  margin-top: 16px;
}

/* 响应式调整 */
@media (max-width: 992px) {
  .task-container {
    grid-template-columns: 1fr;
  }
  
  .info-grid, .config-items {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 576px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .header-right {
    margin-top: 16px;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
}
</style> 