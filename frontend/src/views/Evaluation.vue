<template>
  <div class="evaluation-page">
    <div class="page-header">
      <h1>模型评估</h1>
      <div class="actions">
        <button class="btn btn-primary" @click="showCreateTaskModal = true">
          <span class="material-icons">add</span> 新建评估任务
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
      <button class="btn btn-primary" @click="loadTasks">重试</button>
    </div>

    <!-- 没有任务 -->
    <div v-else-if="tasks.length === 0" class="empty-container">
      <div class="empty-icon">
        <span class="material-icons">analytics_off</span>
      </div>
      <p>您还没有创建任何评估任务</p>
      <button class="btn btn-primary" @click="showCreateTaskModal = true">
        创建第一个评估任务
      </button>
    </div>

    <!-- 任务列表 -->
    <div v-else class="tasks-container">
      <div class="tasks-grid">
        <div v-for="task in tasks" :key="task.id" class="task-card" :class="{ 'running': task.status === 'RUNNING' }">
          <div class="task-header">
            <h3 class="task-name" :title="task.name">{{ task.name }}</h3>
            <div class="task-status" :class="getStatusClass(task.status)">
              {{ getStatusText(task.status) }}
            </div>
          </div>
          
          <div class="task-details">
            <div class="detail-item">
              <span class="label">基准测试:</span>
              <span class="value">{{ getBenchmarkName(task.benchmark_type) }}</span>
            </div>
            <div class="detail-item">
              <span class="label">示例数量:</span>
              <span class="value">{{ task.num_fewshot }}</span>
            </div>
            <div class="detail-item">
              <span class="label">创建时间:</span>
              <span class="value">{{ formatDate(task.created_at) }}</span>
            </div>
          </div>
          
          <div class="task-progress" v-if="task.status === 'RUNNING' || task.status === 'DOWNLOADING'">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: `${task.progress * 100}%` }"></div>
            </div>
            <div class="progress-text">{{ Math.round(task.progress * 100) }}%</div>
          </div>
          
          <div class="task-actions">
            <router-link :to="`/evaluation/${task.id}`" class="btn btn-secondary">
              查看详情
            </router-link>
            <button v-if="task.status === 'PENDING' || task.status === 'FAILED' || task.status === 'STOPPED'"
                    class="btn btn-primary" @click="startTask(task.id)">
              开始评估
            </button>
            <button v-if="task.status === 'RUNNING'"
                    class="btn btn-warning" @click="stopTask(task.id)">
              停止评估
            </button>
            <button v-if="task.status !== 'RUNNING'" 
                    class="btn btn-danger" @click="confirmDeleteTask(task.id)">
              删除
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 创建任务的模态框 -->
    <div v-if="showCreateTaskModal" class="modal-overlay" @click.self="showCreateTaskModal = false">
      <div class="modal-container">
        <div class="modal-header">
          <h2>创建评估任务</h2>
          <button class="btn-icon" @click="showCreateTaskModal = false">
            <span class="material-icons">close</span>
          </button>
        </div>
        
        <div class="modal-body">
          <div class="form-group">
            <label for="taskName">任务名称</label>
            <input type="text" id="taskName" v-model="newTask.name" class="form-control" placeholder="输入评估任务名称">
          </div>
          
          <div class="form-group">
            <label for="modelSelect">选择模型</label>
            <select id="modelSelect" v-model="newTask.model_id" class="form-control">
              <option value="" disabled>请选择模型</option>
              <option v-for="model in availableModels" :key="model.id" :value="model.id">
                {{ model.name }}
              </option>
            </select>
          </div>
          
          <div class="form-group">
            <label for="benchmarkType">基准测试类型</label>
            <select id="benchmarkType" v-model="newTask.benchmark_type" class="form-control">
              <option value="" disabled>请选择基准测试</option>
              <optgroup v-for="category in groupedBenchmarks" :key="category.name" :label="category.name">
                <option v-for="benchmark in category.benchmarks" :key="benchmark.id" :value="benchmark.id">
                  {{ benchmark.name }} - {{ benchmark.description }}
                </option>
              </optgroup>
            </select>
          </div>
          
          <div class="form-group">
            <label for="numFewshot">少样本示例数量</label>
            <input type="number" id="numFewshot" v-model.number="newTask.num_fewshot" class="form-control" min="0" max="20">
            <small class="form-text text-muted">模型在执行任务前会看到的示例数量，通常设置为0-5</small>
          </div>
          
          <div class="form-group" v-if="newTask.benchmark_type === 'custom'">
            <label for="customDataset">自定义数据集路径</label>
            <input type="text" id="customDataset" v-model="newTask.custom_dataset_path" class="form-control" placeholder="输入数据集路径">
            <small class="form-text text-muted">只有选择自定义测试时需要填写</small>
          </div>
        </div>
        
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showCreateTaskModal = false">取消</button>
          <button class="btn btn-primary" @click="createTask" :disabled="!isFormValid">创建任务</button>
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
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { evaluation, resources } from '@/api/client.ts'
import { useToast } from '@/composables/toast'

export default {
  name: 'Evaluation',
  setup() {
    const router = useRouter()
    const { showToast } = useToast()
    
    // 状态变量
    const tasks = ref([])
    const loading = ref(true)
    const error = ref(null)
    const availableModels = ref([])
    const availableBenchmarks = ref([])
    const showCreateTaskModal = ref(false)
    const showDeleteModal = ref(false)
    const taskToDelete = ref(null)
    
    // 新任务表单
    const newTask = ref({
      name: '',
      model_id: '',
      benchmark_type: '',
      num_fewshot: 0,
      custom_dataset_path: '',
    })
    
    // 分组后的基准测试
    const groupedBenchmarks = computed(() => {
      const groups = {}
      
      availableBenchmarks.value.forEach(benchmark => {
        if (!groups[benchmark.category]) {
          groups[benchmark.category] = {
            name: benchmark.category,
            benchmarks: []
          }
        }
        
        groups[benchmark.category].benchmarks.push(benchmark)
      })
      
      return Object.values(groups)
    })
    
    // 表单验证
    const isFormValid = computed(() => {
      if (!newTask.value.name || !newTask.value.model_id || !newTask.value.benchmark_type) {
        return false
      }
      
      if (newTask.value.benchmark_type === 'custom' && !newTask.value.custom_dataset_path) {
        return false
      }
      
      return true
    })
    
    // 获取任务列表
    const loadTasks = async () => {
      loading.value = true
      error.value = null
      
      try {
        const response = await evaluation.getTasks()
        tasks.value = response.data
      } catch (err) {
        console.error('加载评估任务失败:', err)
        error.value = '加载评估任务失败，请稍后重试'
      } finally {
        loading.value = false
      }
    }
    
    // 加载可用模型
    const loadModels = async () => {
      try {
        const response = await resources.getAll()
        availableModels.value = response.data.filter(
          resource => resource.resource_type === 'MODEL' && resource.status === 'COMPLETED'
        )
      } catch (err) {
        console.error('加载模型列表失败:', err)
        showToast('加载模型列表失败', 'error')
      }
    }
    
    // 加载可用基准测试
    const loadBenchmarks = async () => {
      try {
        const response = await evaluation.getBenchmarks()
        availableBenchmarks.value = response.data
      } catch (err) {
        console.error('加载基准测试列表失败:', err)
        showToast('加载基准测试列表失败', 'error')
      }
    }
    
    // 创建新任务
    const createTask = async () => {
      try {
        await evaluation.createTask(newTask.value)
        showToast('评估任务创建成功', 'success')
        showCreateTaskModal.value = false
        
        // 重置表单
        newTask.value = {
          name: '',
          model_id: '',
          benchmark_type: '',
          num_fewshot: 0,
          custom_dataset_path: '',
        }
        
        // 重新加载任务列表
        loadTasks()
      } catch (err) {
        console.error('创建评估任务失败:', err)
        showToast(err.response?.data?.detail || '创建评估任务失败', 'error')
      }
    }
    
    // 开始任务
    const startTask = async (taskId) => {
      try {
        await evaluation.startTask(taskId)
        showToast('评估任务已开始', 'success')
        loadTasks()
      } catch (err) {
        console.error('启动评估任务失败:', err)
        showToast(err.response?.data?.detail || '启动评估任务失败', 'error')
      }
    }
    
    // 停止任务
    const stopTask = async (taskId) => {
      try {
        await evaluation.stopTask(taskId)
        showToast('评估任务已停止', 'success')
        loadTasks()
      } catch (err) {
        console.error('停止评估任务失败:', err)
        showToast(err.response?.data?.detail || '停止评估任务失败', 'error')
      }
    }
    
    // 确认删除
    const confirmDeleteTask = (taskId) => {
      taskToDelete.value = taskId
      showDeleteModal.value = true
    }
    
    // 删除任务
    const deleteTask = async () => {
      if (!taskToDelete.value) return
      
      try {
        await evaluation.deleteTask(taskToDelete.value)
        showToast('评估任务已删除', 'success')
        showDeleteModal.value = false
        taskToDelete.value = null
        loadTasks()
      } catch (err) {
        console.error('删除评估任务失败:', err)
        showToast(err.response?.data?.detail || '删除评估任务失败', 'error')
      }
    }
    
    // 格式化日期
    const formatDate = (dateString) => {
      if (!dateString) return '未开始'
      const date = new Date(dateString)
      return date.toLocaleString('zh-CN')
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
    
    // 获取基准测试名称
    const getBenchmarkName = (benchmarkId) => {
      const benchmark = availableBenchmarks.value.find(b => b.id === benchmarkId)
      return benchmark ? benchmark.name : benchmarkId
    }
    
    // 页面加载时获取数据
    onMounted(() => {
      loadTasks()
      loadModels()
      loadBenchmarks()
    })
    
    return {
      tasks,
      loading,
      error,
      availableModels,
      availableBenchmarks,
      groupedBenchmarks,
      showCreateTaskModal,
      showDeleteModal,
      newTask,
      isFormValid,
      loadTasks,
      createTask,
      startTask,
      stopTask,
      confirmDeleteTask,
      deleteTask,
      formatDate,
      getStatusText,
      getStatusClass,
      getBenchmarkName
    }
  }
}
</script>

<style scoped>
.evaluation-page {
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.loading-container, .error-container, .empty-container {
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

.dark-theme .loading-spinner {
  border-color: rgba(255, 255, 255, 0.1);
  border-top-color: var(--primary);
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
  color: var(--text-secondary);
}

.empty-icon .material-icons {
  font-size: 64px;
}

/* 任务卡片网格 */
.tasks-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 24px;
}

.task-card {
  background-color: var(--surface);
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition: all 0.2s ease;
  border-left: 4px solid var(--primary);
}

.dark-theme .task-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.task-card.running {
  border-left-color: var(--warning);
}

.task-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.dark-theme .task-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.task-name {
  font-size: 18px;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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

.task-details {
  margin-bottom: 16px;
}

.detail-item {
  display: flex;
  margin-bottom: 4px;
}

.detail-item .label {
  flex: 0 0 100px;
  color: var(--text-secondary);
}

.detail-item .value {
  flex: 1;
}

.task-progress {
  margin-bottom: 16px;
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

.task-actions {
  display: flex;
  justify-content: space-between;
  gap: 8px;
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
  background-color: #ffffff;
  border-radius: 8px;
  width: 500px;
  max-width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}

.dark-theme .modal-container {
  background-color: #303030;
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

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
}

.form-control {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background-color: var(--surface);
  color: var(--text-primary);
  font-size: 14px;
}

.dark-theme .form-control {
  background-color: var(--surface-variant);
}

.form-control:focus {
  border-color: var(--primary);
  outline: none;
}

.form-text {
  font-size: 12px;
  margin-top: 4px;
}

/* 响应式调整 */
@media (max-width: 768px) {
  .tasks-grid {
    grid-template-columns: 1fr;
  }
  
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
}
</style> 