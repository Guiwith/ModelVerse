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
      <div v-if="task.status === 'COMPLETED'" class="results-card">
        <div class="card-header">
          <h2>评估结果(当前版本评估结果仅供参考)</h2>
        </div>
        
        <div v-if="task.metrics && Object.keys(task.metrics).length > 0" class="metrics-container">
          <div v-if="task.metrics.accuracy !== undefined && task.metrics.accuracy !== null" class="metric-item">
            <div class="metric-label">准确率</div>
            <div class="metric-value">{{ formatMetric(task.metrics.accuracy) }}</div>
          </div>
          
          <div v-if="task.metrics.f1_score !== undefined && task.metrics.f1_score !== null" class="metric-item">
            <div class="metric-label">F1分数</div>
            <div class="metric-value">{{ formatMetric(task.metrics.f1_score) }}</div>
          </div>
          
          <div v-if="task.metrics.precision !== undefined && task.metrics.precision !== null" class="metric-item">
            <div class="metric-label">精确率</div>
            <div class="metric-value">{{ formatMetric(task.metrics.precision) }}</div>
          </div>
          
          <div v-if="task.metrics.recall !== undefined && task.metrics.recall !== null" class="metric-item">
            <div class="metric-label">召回率</div>
            <div class="metric-value">{{ formatMetric(task.metrics.recall) }}</div>
          </div>
          
          <div v-if="task.metrics.perplexity !== undefined && task.metrics.perplexity !== null" class="metric-item">
            <div class="metric-label">困惑度</div>
            <div class="metric-value">{{ formatNumber(task.metrics.perplexity) }}</div>
          </div>
          
          <div v-if="task.metrics.bleu !== undefined && task.metrics.bleu !== null" class="metric-item">
            <div class="metric-label">BLEU分数</div>
            <div class="metric-value">{{ formatMetric(task.metrics.bleu) }}</div>
          </div>
          
          <div v-if="task.metrics.rouge !== undefined && task.metrics.rouge !== null" class="metric-item">
            <div class="metric-label">ROUGE分数</div>
            <div class="metric-value">{{ formatMetric(task.metrics.rouge) }}</div>
          </div>
          
          <div v-if="task.metrics.exact_match !== undefined && task.metrics.exact_match !== null" class="metric-item">
            <div class="metric-label">精确匹配率</div>
            <div class="metric-value">{{ formatMetric(task.metrics.exact_match) }}</div>
          </div>
          
          <!-- 自定义指标 -->
          <template v-if="task.metrics.custom_metrics">
            <div v-for="(value, key) in task.metrics.custom_metrics" :key="key" class="metric-item" v-if="formatMetricName(key) !== null">
              <div class="metric-label">{{ formatMetricName(key) }}</div>
              <div class="metric-value">{{ formatMetricValue(value) }}</div>
            </div>
          </template>
          
          <!-- 处理直接在metrics对象上的自定义指标 -->
          <template v-if="task.metrics">
            <div v-for="(value, key) in task.metrics" :key="key" class="metric-item" 
                v-if="!['accuracy', 'f1_score', 'precision', 'recall', 'perplexity', 'bleu', 'rouge', 'exact_match', 'custom_metrics'].includes(key) && formatMetricName(key) !== null">
              <div class="metric-label">{{ formatMetricName(key) }}</div>
              <div class="metric-value">{{ formatMetricValue(value) }}</div>
            </div>
          </template>
        </div>
        <div v-else class="metrics-empty">
          <p>正在加载评估结果，请稍候...</p>
          <button class="btn btn-primary btn-sm" @click="loadTask">
            <span class="material-icons">refresh</span> 刷新
          </button>
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
import { getApiBaseUrl } from '@/config'

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
    let updateInterval = null
    
    // 加载任务详情
    const loadTask = async () => {
      loading.value = true
      error.value = null
      
      try {
        console.log('加载任务详情:', taskId)
        const response = await evaluation.getTaskById(taskId)
        
        // 检查返回的数据是否有效
        if (response.data) {
          console.log('成功加载任务数据:', response.data)
          
          // 如果当前有指标数据但新数据没有，保留当前指标
          if (task.value && task.value.metrics && 
              response.data.status === 'COMPLETED' && 
              (!response.data.metrics || Object.keys(response.data.metrics).length === 0)) {
            console.log('保留当前指标数据，新数据没有指标')
            response.data.metrics = task.value.metrics
          }
          
          task.value = response.data
          
          // 如果任务已完成且没有指标数据，尝试再次加载
          if (task.value.status === 'COMPLETED' && (!task.value.metrics || Object.keys(task.value.metrics).length === 0)) {
            console.log('任务已完成但未检测到指标数据，3秒后重新加载')
            setTimeout(() => {
              loadTask()
            }, 3000)
          }
          
          // 如果任务正在运行，连接WebSocket
          if (task.value.status === 'RUNNING') {
            connectWebSocket()
          }
        } else {
          console.error('任务数据为空')
          error.value = '加载评估任务详情失败，获取到空数据'
        }
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
      const apiBaseUrl = getApiBaseUrl();
      const url = new URL(apiBaseUrl);
      const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
      socket = new WebSocket(`${protocol}//${url.host}/ws/evaluation/${taskId}`)
      
      // 连接打开
      socket.onopen = () => {
        console.log('WebSocket连接已建立')
      }
      
      // 接收消息
      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          console.log('收到WebSocket消息:', data)
          
          // 处理不同类型的消息
          if (data.type === 'task_status') {
            // 更新任务状态
            if (task.value) {
              console.log('更新任务状态:', data.data)
              
              // 先保存当前的指标，以便在需要时保留
              const currentMetrics = task.value.metrics ? {...task.value.metrics} : null
              
              // 更新状态信息
              task.value.status = data.data.status
              task.value.progress = data.data.progress
              task.value.error_message = data.data.error_message
              
              // 如果完成时间不存在但状态为COMPLETED，添加完成时间
              if (data.data.status === 'COMPLETED' && !task.value.completed_at) {
                task.value.completed_at = new Date().toISOString()
              }
              
              // 如果有指标数据，更新指标
              if (data.data.metrics && Object.keys(data.data.metrics).length > 0) {
                console.log('更新指标数据:', data.data.metrics)
                task.value.metrics = data.data.metrics
              } else if (data.data.status === 'COMPLETED' && (!task.value.metrics || Object.keys(task.value.metrics).length === 0) && currentMetrics) {
                // 如果状态是已完成但没有收到指标数据，保留之前的指标
                console.log('保留当前指标数据:', currentMetrics)
                task.value.metrics = currentMetrics
              }
              
              // 如果状态变为COMPLETED，重新加载任务以获取完整数据
              if (data.data.status === 'COMPLETED') {
                console.log('任务完成，重新加载完整数据')
                setTimeout(() => {
                  loadTask()
                  loadLogs()
                }, 2000)
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
          console.error('解析WebSocket消息失败:', err, '原始数据:', event.data)
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
      try {
        // 防止key为undefined或null
        if (key === undefined || key === null) return null;
        
        // 确保key是字符串类型
        const keyStr = String(key);
        
        // 如果是unknown_rate结尾的指标，不显示
        if (keyStr.endsWith && typeof keyStr.endsWith === 'function' && keyStr.endsWith('_unknown_rate')) {
          return null;
        }

        // 专有名词翻译对照表
        const nameMap = {
          'total_correct': '总正确数',
          'total_questions': '总问题数',
          'total_unknown': '总未知数',
          'unknown_rate': '未知率',
          'accuracy': '准确率',
          'f1_score': 'F1分数',
          'precision': '精确率',
          'recall': '召回率',
          'perplexity': '困惑度',
          'bleu': 'BLEU分数',
          'rouge': 'ROUGE分数',
          'exact_match': '精确匹配率',
          'abstract_algebra_accuracy': '抽象代数准确率',
          'anatomy_accuracy': '解剖学准确率',
          'astronomy_accuracy': '天文学准确率',
          'business_ethics_accuracy': '商业伦理准确率',
          'clinical_knowledge_accuracy': '临床知识准确率',
          'college_biology_accuracy': '大学生物学准确率',
          'college_chemistry_accuracy': '大学化学准确率',
          'college_computer_science_accuracy': '大学计算机科学准确率',
          'college_mathematics_accuracy': '大学数学准确率',
          'college_physics_accuracy': '大学物理学准确率',
          'computer_security_accuracy': '计算机安全准确率',
          'conceptual_physics_accuracy': '概念物理学准确率',
          'econometrics_accuracy': '计量经济学准确率',
          'electrical_engineering_accuracy': '电气工程准确率',
          'elementary_mathematics_accuracy': '小学数学准确率',
          'formal_logic_accuracy': '形式逻辑准确率',
          'global_facts_accuracy': '全球事实准确率',
          'high_school_biology_accuracy': '高中生物学准确率',
          'high_school_chemistry_accuracy': '高中化学准确率',
          'high_school_computer_science_accuracy': '高中计算机科学准确率',
          'high_school_european_history_accuracy': '高中欧洲历史准确率',
          'high_school_geography_accuracy': '高中地理准确率',
          'high_school_government_and_politics_accuracy': '高中政府与政治准确率',
          'high_school_macroeconomics_accuracy': '高中宏观经济学准确率',
          'high_school_mathematics_accuracy': '高中数学准确率',
          'high_school_microeconomics_accuracy': '高中微观经济学准确率',
          'high_school_physics_accuracy': '高中物理学准确率',
          'high_school_psychology_accuracy': '高中心理学准确率',
          'high_school_statistics_accuracy': '高中统计学准确率',
          'high_school_us_history_accuracy': '高中美国历史准确率',
          'high_school_world_history_accuracy': '高中世界历史准确率',
          'human_aging_accuracy': '人类老化准确率',
          'human_sexuality_accuracy': '人类性行为准确率',
          'international_law_accuracy': '国际法准确率',
          'jurisprudence_accuracy': '法理学准确率',
          'logical_fallacies_accuracy': '逻辑谬误准确率',
          'machine_learning_accuracy': '机器学习准确率',
          'management_accuracy': '管理学准确率',
          'marketing_accuracy': '市场营销准确率',
          'medical_genetics_accuracy': '医学遗传学准确率',
          'miscellaneous_accuracy': '杂项准确率',
          'moral_disputes_accuracy': '道德争议准确率',
          'moral_scenarios_accuracy': '道德情景准确率',
          'nutrition_accuracy': '营养学准确率',
          'philosophy_accuracy': '哲学准确率',
          'prehistory_accuracy': '史前史准确率',
          'professional_accounting_accuracy': '专业会计准确率',
          'professional_law_accuracy': '专业法律准确率',
          'professional_medicine_accuracy': '专业医学准确率',
          'professional_psychology_accuracy': '专业心理学准确率',
          'public_relations_accuracy': '公共关系准确率',
          'security_studies_accuracy': '安全研究准确率',
          'sociology_accuracy': '社会学准确率',
          'us_foreign_policy_accuracy': '美国外交政策准确率',
          'virology_accuracy': '病毒学准确率',
          'world_religions_accuracy': '世界宗教准确率'
        };

        // 检查是否有直接映射
        if (nameMap[keyStr]) {
          return nameMap[keyStr];
        }

        // 将snake_case转换为标题形式
        if (keyStr.split && typeof keyStr.split === 'function') {
          return keyStr.split('_').map(word => {
            if (word && typeof word === 'string' && word.charAt && typeof word.charAt === 'function') {
              return word.charAt(0).toUpperCase() + word.slice(1);
            }
            return word;
          }).join(' ');
        }
        
        // 如果无法处理，返回原始键名
        return keyStr;
      } catch (error) {
        console.error('格式化指标名称时出错:', error, '键名:', key);
        return String(key || '未知指标');
      }
    }
    
    // 格式化指标值
    const formatMetricValue = (value) => {
      try {
        if (value === null || value === undefined) return '未知'
        if (typeof value === 'number') {
          if (value >= 0 && value <= 1) {
            return formatMetric(value)
          }
          return formatNumber(value)
        }
        return String(value)
      } catch (error) {
        console.error('格式化指标值时出错:', error, '值:', value);
        return '未知';
      }
    }
    
    // 页面加载时获取数据
    onMounted(() => {
      // 初始加载数据
      loadTask()
      loadLogs()
      loadBenchmarks()
      
      // 设置定期更新机制
      updateInterval = setInterval(() => {
        if (task.value && task.value.status === 'RUNNING') {
          console.log('定期更新任务状态')
          loadTask()
          loadLogs()
        } else if (task.value && task.value.status === 'COMPLETED' && (!task.value.metrics || Object.keys(task.value.metrics).length === 0)) {
          console.log('任务完成但指标为空，尝试重新加载')
          loadTask()
        } else if (task.value && task.value.status !== 'RUNNING') {
          console.log('任务不再运行，清除定时更新')
          clearInterval(updateInterval)
        }
      }, 10000)
      
      // 如果任务正在运行，连接WebSocket
      setTimeout(() => {
        if (task.value && task.value.status === 'RUNNING') {
          console.log('自动连接WebSocket')
          connectWebSocket()
        }
      }, 1000)
    })
    
    // 页面卸载时关闭WebSocket和清理定时器
    onUnmounted(() => {
      if (updateInterval) {
        clearInterval(updateInterval)
      }
      
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
  background-color: #ffffff !important;
  border-radius: 8px;
  width: 400px;
  max-width: 90%;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}

.dark-theme .modal-container {
  background-color: #2d2d2d !important;
  color: #ffffff;
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
  background-color: #3a3a3a !important;
  color: #ffffff !important;
  border-color: #555555;
}

.dark-theme select:focus {
  outline-color: #007bff;
}

.dark-theme select option {
  background-color: #3a3a3a !important;
  color: #ffffff !important;
}

.metrics-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: var(--text-secondary);
  gap: 16px;
}

.metrics-empty p {
  margin: 0;
}
</style> 