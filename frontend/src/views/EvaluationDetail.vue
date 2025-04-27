<template>
  <div class="evaluation-detail-page">
    <div class="page-header">
      <div class="title-section">
        <router-link to="/evaluation" class="back-link">
          <span class="material-icons">arrow_back</span>
        </router-link>
        <h1 v-if="task">{{ task.name }}</h1>
        <h1 v-else>评估任务详情</h1>
      </div>

      <div v-if="task" class="actions">
        <button v-if="task.status === 'PENDING' || task.status === 'FAILED' || task.status === 'STOPPED'"
                class="btn btn-primary" @click="startTask">
          <span class="material-icons">play_arrow</span> 开始评估
        </button>
        <button v-if="task.status === 'RUNNING'"
                class="btn btn-warning" @click="stopTask">
          <span class="material-icons">stop</span> 停止评估
        </button>
        <button v-if="task.status !== 'RUNNING'" 
                class="btn btn-danger" @click="confirmDeleteTask">
          <span class="material-icons">delete</span> 删除
        </button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <div class="loading-spinner"></div>
      <p>加载中...</p>
    </div>

    <!-- 错误信息 -->
    <div v-else-if="error" class="error-container">
      <p>{{ error }}</p>
      <button class="btn btn-primary" @click="loadTask">重试</button>
    </div>

    <!-- 任务详情 -->
    <div v-else-if="task" class="task-detail-container">
      <div class="task-info-card">
        <div class="card-header">
          <h2>任务信息</h2>
          <div class="task-status" :class="getStatusClass(task.status)">
            {{ getStatusText(task.status) }}
          </div>
        </div>
        
        <div class="task-info-grid">
          <div class="info-item">
            <div class="info-label">基准测试</div>
            <div class="info-value">{{ getBenchmarkInfo(task.benchmark_type) }}</div>
          </div>
          
          <div class="info-item">
            <div class="info-label">示例数量</div>
            <div class="info-value">{{ task.num_fewshot || 0 }}</div>
          </div>
          
          <div class="info-item">
            <div class="info-label">创建时间</div>
            <div class="info-value">{{ formatDate(task.created_at) }}</div>
          </div>
          
          <div class="info-item">
            <div class="info-label">开始时间</div>
            <div class="info-value">{{ formatDate(task.started_at) || '未开始' }}</div>
          </div>
          
          <div class="info-item">
            <div class="info-label">完成时间</div>
            <div class="info-value">{{ formatDate(task.completed_at) || '未完成' }}</div>
          </div>
          
          <div class="info-item" v-if="task.error_message">
            <div class="info-label">错误信息</div>
            <div class="info-value error-message">{{ task.error_message }}</div>
          </div>
        </div>
        
        <div v-if="task.status === 'RUNNING'" class="task-progress">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: `${task.progress * 100}%` }"></div>
          </div>
          <div class="progress-text">{{ Math.round(task.progress * 100) }}%</div>
        </div>
      </div>
      
      <!-- 评估结果 -->
      <div v-if="task.status === 'COMPLETED' && task.metrics" class="results-card">
        <div class="card-header">
          <h2>评估结果</h2>
        </div>
        
        <div class="metrics-container">
          <div v-if="task.metrics.accuracy !== null" class="metric-item">
            <div class="metric-label">准确率</div>
            <div class="metric-value">{{ formatMetric(task.metrics.accuracy) }}</div>
          </div>
          
          <div v-if="task.metrics.f1_score !== null" class="metric-item">
            <div class="metric-label">F1分数</div>
            <div class="metric-value">{{ formatMetric(task.metrics.f1_score) }}</div>
          </div>
          
          <div v-if="task.metrics.precision !== null" class="metric-item">
            <div class="metric-label">精确率</div>
            <div class="metric-value">{{ formatMetric(task.metrics.precision) }}</div>
          </div>
          
          <div v-if="task.metrics.recall !== null" class="metric-item">
            <div class="metric-label">召回率</div>
            <div class="metric-value">{{ formatMetric(task.metrics.recall) }}</div>
          </div>
          
          <div v-if="task.metrics.perplexity !== null" class="metric-item">
            <div class="metric-label">困惑度</div>
            <div class="metric-value">{{ formatNumber(task.metrics.perplexity) }}</div>
          </div>
          
          <div v-if="task.metrics.bleu !== null" class="metric-item">
            <div class="metric-label">BLEU分数</div>
            <div class="metric-value">{{ formatMetric(task.metrics.bleu) }}</div>
          </div>
          
          <div v-if="task.metrics.rouge !== null" class="metric-item">
            <div class="metric-label">ROUGE分数</div>
            <div class="metric-value">{{ formatMetric(task.metrics.rouge) }}</div>
          </div>
          
          <div v-if="task.metrics.exact_match !== null" class="metric-item">
            <div class="metric-label">精确匹配率</div>
            <div class="metric-value">{{ formatMetric(task.metrics.exact_match) }}</div>
          </div>
          
          <!-- 自定义指标 -->
          <template v-if="task.metrics.custom_metrics">
            <div v-for="(value, key) in task.metrics.custom_metrics" :key="key" class="metric-item">
              <div class="metric-label">{{ formatMetricName(key) }}</div>
              <div class="metric-value">{{ formatMetricValue(value) }}</div>
            </div>
          </template>
        </div>
      </div>
      
      <!-- 评估日志 -->
      <div class="logs-card">
        <div class="card-header">
          <h2>评估日志</h2>
          <button class="btn btn-secondary btn-sm" @click="loadLogs">
            <span class="material-icons">refresh</span> 刷新
          </button>
        </div>
        
        <div v-if="logsLoading" class="logs-loading">
          <div class="loading-spinner small"></div>
          <span>加载日志中...</span>
        </div>
        
        <div v-else-if="logsError" class="logs-error">
          <p>{{ logsError }}</p>
          <button class="btn btn-primary btn-sm" @click="loadLogs">重试</button>
        </div>
        
        <div v-else-if="logs.length === 0" class="logs-empty">
          <p>暂无日志</p>
        </div>
        
        <div v-else class="logs-container">
          <div v-for="(log, index) in logs" :key="index" class="log-item" :class="getLogLevelClass(log.level)">
            <div class="log-timestamp">{{ formatTime(log.timestamp) }}</div>
            <div class="log-content">{{ log.content }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 确认删除的模态框 -->
    <div v-if="showDeleteModal" class="modal-overlay" @click.self="showDeleteModal = false">
      <div class="modal-container">
        <div class="modal-header">
          <h2>确认删除</h2>
          <button class="btn-icon" @click="showDeleteModal = false">
            <span class="material-icons">close</span>
          </button>
        </div>
        
        <div class="modal-body">
          <p>您确定要删除这个评估任务吗？此操作无法撤销。</p>
        </div>
        
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showDeleteModal = false">取消</button>
          <button class="btn btn-danger" @click="deleteTask">确认删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { evaluation } from '@/api/client.ts'
import { useToast } from '@/composables/toast'

export default {
  name: 'EvaluationDetail',
  setup() {
    const route = useRoute()
    const router = useRouter()
    const { showToast } = useToast()
    
    // 任务ID
    const taskId = route.params.id
    
    // 状态变量
    const task = ref(null)
    const loading = ref(true)
    const error = ref(null)
    const logs = ref([])
    const logsLoading = ref(false)
    const logsError = ref(null)
    const showDeleteModal = ref(false)
    const availableBenchmarks = ref([])
    
    // WebSocket连接
    let socket = null
    
    // 加载任务详情
    const loadTask = async () => {
      loading.value = true
      error.value = null
      
      try {
        const response = await evaluation.getTaskById(taskId)
        task.value = response.data
      } catch (err) {
        console.error('加载评估任务详情失败:', err)
        error.value = '加载评估任务详情失败，请稍后重试'
      } finally {
        loading.value = false
      }
    }
    
    // 加载评估日志
    const loadLogs = async () => {
      logsLoading.value = true
      logsError.value = null
      
      try {
        const response = await evaluation.getLogs(taskId)
        logs.value = response.data
      } catch (err) {
        console.error('加载评估日志失败:', err)
        logsError.value = '加载评估日志失败，请稍后重试'
      } finally {
        logsLoading.value = false
      }
    }
    
    // 加载基准测试
    const loadBenchmarks = async () => {
      try {
        const response = await evaluation.getBenchmarks()
        availableBenchmarks.value = response.data
      } catch (err) {
        console.error('加载基准测试列表失败:', err)
      }
    }
    
    // 开始评估任务
    const startTask = async () => {
      try {
        await evaluation.startTask(taskId)
        showToast('评估任务已开始', 'success')
        loadTask()
        
        // 连接WebSocket
        connectWebSocket()
      } catch (err) {
        console.error('启动评估任务失败:', err)
        showToast(err.response?.data?.detail || '启动评估任务失败', 'error')
      }
    }
    
    // 停止评估任务
    const stopTask = async () => {
      try {
        await evaluation.stopTask(taskId)
        showToast('评估任务已停止', 'success')
        loadTask()
      } catch (err) {
        console.error('停止评估任务失败:', err)
        showToast(err.response?.data?.detail || '停止评估任务失败', 'error')
      }
    }
    
    // 确认删除
    const confirmDeleteTask = () => {
      showDeleteModal.value = true
    }
    
    // 删除任务
    const deleteTask = async () => {
      try {
        await evaluation.deleteTask(taskId)
        showToast('评估任务已删除', 'success')
        showDeleteModal.value = false
        
        // 跳转回评估任务列表页
        router.push('/evaluation')
      } catch (err) {
        console.error('删除评估任务失败:', err)
        showToast(err.response?.data?.detail || '删除评估任务失败', 'error')
      }
    }
    
    // 连接WebSocket
    const connectWebSocket = () => {
      // 关闭已有连接
      if (socket) {
        socket.close()
      }
      
      // 创建新连接
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.host
      socket = new WebSocket(`${protocol}//${host}/ws/evaluation/${taskId}`)
      
      // 连接打开
      socket.onopen = () => {
        console.log('WebSocket连接已建立')
      }
      
      // 接收消息
      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          // 处理不同类型的消息
          if (data.type === 'task_status') {
            // 更新任务状态
            if (task.value) {
              task.value.status = data.data.status
              task.value.progress = data.data.progress
              task.value.error_message = data.data.error_message
              
              // 如果有指标数据，更新指标
              if (data.data.metrics) {
                task.value.metrics = data.data.metrics
              }
            }
          } else if (data.type === 'logs') {
            // 添加新日志
            if (Array.isArray(data.data)) {
              logs.value = [...data.data, ...logs.value]
            }
          } else if (data.error) {
            console.error('WebSocket错误:', data.error)
          }
        } catch (err) {
          console.error('解析WebSocket消息失败:', err)
        }
      }
      
      // 连接关闭
      socket.onclose = () => {
        console.log('WebSocket连接已关闭')
        
        // 重新加载任务状态和日志
        if (task.value && task.value.status === 'RUNNING') {
          setTimeout(() => {
            loadTask()
            loadLogs()
          }, 5000)
        }
      }
      
      // 连接错误
      socket.onerror = (error) => {
        console.error('WebSocket错误:', error)
      }
    }
    
    // 格式化日期
    const formatDate = (dateString) => {
      if (!dateString) return null
      const date = new Date(dateString)
      return date.toLocaleString('zh-CN')
    }
    
    // 格式化时间
    const formatTime = (dateString) => {
      if (!dateString) return ''
      const date = new Date(dateString)
      return date.toLocaleTimeString('zh-CN')
    }
    
    // 获取状态文本
    const getStatusText = (status) => {
      const statusMap = {
        PENDING: '待处理',
        RUNNING: '运行中',
        COMPLETED: '已完成',
        FAILED: '失败',
        STOPPED: '已停止'
      }
      return statusMap[status] || status
    }
    
    // 获取状态类名
    const getStatusClass = (status) => {
      const classMap = {
        PENDING: 'status-pending',
        RUNNING: 'status-running',
        COMPLETED: 'status-completed',
        FAILED: 'status-failed',
        STOPPED: 'status-stopped'
      }
      return classMap[status] || ''
    }
    
    // 获取日志级别类名
    const getLogLevelClass = (level) => {
      const classMap = {
        INFO: 'log-info',
        WARNING: 'log-warning',
        ERROR: 'log-error',
        DEBUG: 'log-debug'
      }
      return classMap[level] || 'log-info'
    }
    
    // 获取基准测试信息
    const getBenchmarkInfo = (benchmarkId) => {
      const benchmark = availableBenchmarks.value.find(b => b.id === benchmarkId)
      return benchmark ? `${benchmark.name} (${benchmark.description})` : benchmarkId
    }
    
    // 格式化指标值为百分比
    const formatMetric = (value) => {
      if (value === null || value === undefined) return '未知'
      return `${(value * 100).toFixed(2)}%`
    }
    
    // 格式化数字
    const formatNumber = (value) => {
      if (value === null || value === undefined) return '未知'
      return value.toFixed(4)
    }
    
    // 格式化指标名称
    const formatMetricName = (key) => {
      // 将snake_case转换为标题形式
      return key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')
    }
    
    // 格式化指标值
    const formatMetricValue = (value) => {
      if (typeof value === 'number') {
        if (value >= 0 && value <= 1) {
          return formatMetric(value)
        }
        return formatNumber(value)
      }
      return value.toString()
    }
    
    // 页面加载时获取数据
    onMounted(() => {
      loadTask()
      loadLogs()
      loadBenchmarks()
      
      // 如果任务正在运行，连接WebSocket
      setTimeout(() => {
        if (task.value && task.value.status === 'RUNNING') {
          connectWebSocket()
        }
      }, 1000)
    })
    
    // 页面卸载时关闭WebSocket
    onUnmounted(() => {
      if (socket) {
        socket.close()
      }
    })
    
    return {
      task,
      loading,
      error,
      logs,
      logsLoading,
      logsError,
      showDeleteModal,
      loadTask,
      loadLogs,
      startTask,
      stopTask,
      confirmDeleteTask,
      deleteTask,
      formatDate,
      formatTime,
      getStatusText,
      getStatusClass,
      getLogLevelClass,
      getBenchmarkInfo,
      formatMetric,
      formatNumber,
      formatMetricName,
      formatMetricValue
    }
  }
}
</script>

<style scoped>
.evaluation-detail-page {
  max-width: 1000px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.title-section {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-link {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-primary);
  text-decoration: none;
  width: 40px;
  height: 40px;
  border-radius: 20px;
  transition: background-color 0.2s;
}

.back-link:hover {
  background-color: var(--surface-variant);
}

.loading-container, .error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  text-align: center;
}

.loading-spinner {
  border: 4px solid rgba(0, 0, 0, 0.1);
  border-top: 4px solid var(--primary);
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

.loading-spinner.small {
  width: 20px;
  height: 20px;
  border-width: 2px;
  margin-bottom: 0;
  margin-right: 8px;
}

.dark-theme .loading-spinner {
  border-color: rgba(255, 255, 255, 0.1);
  border-top-color: var(--primary);
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.task-detail-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.task-info-card, .results-card, .logs-card {
  background-color: var(--surface);
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.dark-theme .task-info-card,
.dark-theme .results-card,
.dark-theme .logs-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.card-header h2 {
  margin: 0;
  font-size: 18px;
}

.task-status {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 4px;
}

.status-pending {
  background-color: var(--info-subtle);
  color: var(--info);
}

.status-running {
  background-color: var(--warning-subtle);
  color: var(--warning);
}

.status-completed {
  background-color: var(--success-subtle);
  color: var(--success);
}

.status-failed {
  background-color: var(--error-subtle);
  color: var(--error);
}

.status-stopped {
  background-color: var(--secondary-subtle);
  color: var(--secondary);
}

.task-info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.info-item {
  margin-bottom: 8px;
}

.info-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.info-value {
  font-size: 14px;
}

.error-message {
  color: var(--error);
}

.task-progress {
  margin-top: 16px;
}

.progress-bar {
  height: 6px;
  background-color: var(--surface-variant);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 4px;
}

.progress-fill {
  height: 100%;
  background-color: var(--primary);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-text {
  text-align: right;
  font-size: 12px;
  color: var(--text-secondary);
}

/* 评估结果 */
.metrics-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 16px;
}

.metric-item {
  background-color: var(--surface-variant);
  padding: 12px;
  border-radius: 6px;
  text-align: center;
}

.metric-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.metric-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--primary);
}

/* 日志显示 */
.logs-loading, .logs-error, .logs-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: var(--text-secondary);
}

.logs-container {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background-color: var(--surface-variant);
  padding: 8px;
  font-family: monospace;
  font-size: 12px;
}

.log-item {
  display: flex;
  margin-bottom: 4px;
  padding: 4px;
  border-radius: 4px;
}

.log-timestamp {
  flex: 0 0 80px;
  color: var(--text-secondary);
  margin-right: 8px;
}

.log-content {
  flex: 1;
  word-break: break-word;
}

.log-info {
  background-color: transparent;
}

.log-warning {
  background-color: var(--warning-subtle);
  color: var(--warning);
}

.log-error {
  background-color: var(--error-subtle);
  color: var(--error);
}

.log-debug {
  background-color: var(--info-subtle);
  color: var(--info);
}

/* 模态框样式 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-container {
  background-color: var(--surface);
  border-radius: 8px;
  width: 400px;
  max-width: 90%;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}

.dark-theme .modal-container {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h2 {
  margin: 0;
  font-size: 18px;
}

.modal-body {
  padding: 16px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  padding: 16px;
  border-top: 1px solid var(--border-color);
  gap: 8px;
}

/* 响应式调整 */
@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  
  .metrics-container {
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  }
  
  .task-info-grid {
    grid-template-columns: 1fr;
  }
}

/* 下拉框暗色模式适配 */
.dark-theme select,
.dark-theme option {
  background-color: var(--surface);
  color: var(--text-primary);
  border-color: var(--border-color);
}

.dark-theme select:focus {
  outline-color: var(--primary);
}

.dark-theme select option {
  background-color: var(--surface);
  color: var(--text-primary);
}
</style> 