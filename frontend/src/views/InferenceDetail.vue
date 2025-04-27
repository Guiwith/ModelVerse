<template>
  <div class="inference-detail-page">
    <div class="page-header">
      <div class="page-title">
        <router-link to="/inference" class="back-link">
          <span class="material-icons">arrow_back</span>
        </router-link>
        <h1>{{ task ? task.name : '加载中...' }}</h1>
        <div v-if="task" class="task-status" :class="task.status.toLowerCase()">
          {{ getStatusText(task.status) }}
        </div>
      </div>
      <div class="page-actions">
        <button @click="refreshTask" class="btn btn-secondary">
          <span class="material-icons">refresh</span>
          刷新
        </button>
        
        <button @click="startTask" class="btn btn-success" 
                v-if="task && task.status !== 'RUNNING' && task.status !== 'CREATING'">
          <span class="material-icons">play_arrow</span>
          启动
        </button>
        
        <button @click="stopTask" class="btn btn-warning" 
                v-if="task && task.status === 'RUNNING'">
          <span class="material-icons">stop</span>
          停止
        </button>
        
        <router-link :to="`/chat/${taskId}`" class="btn btn-primary" 
                    v-if="task && task.status === 'RUNNING'">
          <span class="material-icons">chat</span>
          聊天
        </router-link>
        
        <button @click="confirmDelete" class="btn btn-danger" 
                v-if="task && task.status !== 'RUNNING' && task.status !== 'CREATING'">
          <span class="material-icons">delete</span>
          删除
        </button>
      </div>
    </div>

    <div v-if="loading" class="loading-container">
      <div class="spinner"></div>
      <p>加载中...</p>
    </div>

    <div v-else-if="!task" class="error-container">
      <span class="material-icons error-icon">error</span>
      <h2>无法加载推理任务</h2>
      <p>无法找到ID为 {{ taskId }} 的推理任务或您没有权限访问</p>
      <router-link to="/inference" class="btn btn-primary">返回推理任务列表</router-link>
    </div>

    <div v-else class="task-details">
      <div class="section task-info-section">
        <h2>基本信息</h2>
        <div class="info-grid">
          <div class="info-item">
            <div class="info-label">任务ID</div>
            <div class="info-value">{{ task.id }}</div>
          </div>
          
          <div class="info-item">
            <div class="info-label">模型</div>
            <div class="info-value">{{ modelName }}</div>
          </div>
          
          <div class="info-item">
            <div class="info-label">状态</div>
            <div class="info-value status" :class="task.status.toLowerCase()">
              {{ getStatusText(task.status) }}
            </div>
          </div>
          
          <div class="info-item">
            <div class="info-label">创建时间</div>
            <div class="info-value">{{ formatDateTime(task.created_at) }}</div>
          </div>
          
          <div class="info-item" v-if="task.started_at">
            <div class="info-label">启动时间</div>
            <div class="info-value">{{ formatDateTime(task.started_at) }}</div>
          </div>
          
          <div class="info-item" v-if="task.stopped_at">
            <div class="info-label">停止时间</div>
            <div class="info-value">{{ formatDateTime(task.stopped_at) }}</div>
          </div>
          
          <div class="info-item" v-if="task.process_id && task.status === 'RUNNING'">
            <div class="info-label">进程ID</div>
            <div class="info-value">{{ task.process_id }}</div>
          </div>
          
          <div class="info-item" v-if="task.port && task.status === 'RUNNING'">
            <div class="info-label">服务端口</div>
            <div class="info-value">{{ task.port }}</div>
          </div>
          
          <div class="info-item" v-if="task.api_base && task.status === 'RUNNING'">
            <div class="info-label">API地址</div>
            <div class="info-value code">{{ task.api_base }}</div>
          </div>
          
          <div class="info-item" v-if="task.gpu_memory">
            <div class="info-label">显存占用</div>
            <div class="info-value">{{ formatMemory(task.gpu_memory) }}</div>
          </div>
        </div>
        
        <div class="error-message" v-if="task.error_message">
          <h3>错误信息</h3>
          <div class="error-content">{{ task.error_message }}</div>
        </div>
      </div>
      
      <div class="section model-section">
        <h2>模型配置</h2>
        <div class="info-grid">
          <div class="info-item">
            <div class="info-label">Tensor并行大小</div>
            <div class="info-value">{{ task.tensor_parallel_size }}</div>
          </div>
          
          <div class="info-item">
            <div class="info-label">最大模型长度</div>
            <div class="info-value">{{ task.max_model_len }}</div>
          </div>
          
          <div class="info-item">
            <div class="info-label">量化方法</div>
            <div class="info-value">{{ task.quantization || '未量化' }}</div>
          </div>
          
          <div class="info-item">
            <div class="info-label">数据类型</div>
            <div class="info-value">{{ task.dtype }}</div>
          </div>
        </div>
      </div>
      
      <div class="section params-section">
        <h2>推理参数</h2>
        <div class="info-grid">
          <div class="info-item">
            <div class="info-label">最大输出Token</div>
            <div class="info-value">{{ task.max_tokens }}</div>
          </div>
          
          <div class="info-item">
            <div class="info-label">温度</div>
            <div class="info-value">{{ task.temperature }}</div>
          </div>
          
          <div class="info-item">
            <div class="info-label">Top P</div>
            <div class="info-value">{{ task.top_p }}</div>
          </div>
          
          <div class="info-item">
            <div class="info-label">Top K</div>
            <div class="info-value">{{ task.top_k }}</div>
          </div>
          
          <div class="info-item">
            <div class="info-label">重复惩罚</div>
            <div class="info-value">{{ task.repetition_penalty }}</div>
          </div>
          
          <div class="info-item">
            <div class="info-label">Presence惩罚</div>
            <div class="info-value">{{ task.presence_penalty }}</div>
          </div>
          
          <div class="info-item">
            <div class="info-label">Frequency惩罚</div>
            <div class="info-value">{{ task.frequency_penalty }}</div>
          </div>
        </div>
        
        <button @click="showParamsModal = true" class="btn btn-outline">
          <span class="material-icons">edit</span>
          编辑参数
        </button>
      </div>
      
      <div class="section share-section">
        <h2>共享设置</h2>
        <div class="share-description">
          启用共享聊天后，系统将生成一个无需登录即可访问的聊天页面。任何人都可以通过链接访问并与模型对话。
        </div>
        
        <div class="share-controls">
          <label class="switch">
            <input type="checkbox" v-model="shareEnabled" @change="updateShareSettings">
            <span class="slider round"></span>
          </label>
          <span class="switch-label">{{ shareEnabled ? '已启用共享' : '未启用共享' }}</span>
        </div>
        
        <div v-if="shareEnabled" class="share-options">
          <div class="form-group">
            <label for="displayName">模型显示名称</label>
            <input 
              type="text" 
              id="displayName" 
              v-model="displayName" 
              placeholder="输入在共享页面显示的模型名称"
              @blur="updateShareSettings"
            >
            <small>此名称将显示在共享聊天页面上</small>
          </div>
          
          <div class="share-url">
            <div class="url-label">共享链接:</div>
            <div class="url-container">
              <input 
                type="text" 
                readonly 
                :value="shareUrl" 
                ref="shareUrlInput"
              >
              <button @click="copyShareUrl" class="btn btn-icon">
                <span class="material-icons">content_copy</span>
              </button>
            </div>
          </div>
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
          <p>您确定要删除推理任务 <strong>{{ task?.name }}</strong> 吗？此操作无法撤销。</p>
          
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
import { apiClient, inference } from '../api/client'
import { useToast } from '../composables/toast'

export default {
  name: 'InferenceDetailPage',
  setup() {
    const route = useRoute()
    const router = useRouter()
    const { showToast } = useToast()
    
    // 任务ID
    const taskId = parseInt(route.params.id)
    
    // 数据
    const task = ref(null)
    const model = ref(null)
    const loading = ref(true)
    const isUpdating = ref(false)
    const showDeleteModal = ref(false)
    const showParamsModal = ref(false)
    const shareUrlInput = ref(null)
    
    // 共享设置
    const shareEnabled = ref(false)
    const displayName = ref('')
    
    // 刷新定时器
    let refreshTimer = null
    
    // 推理参数
    const params = reactive({
      max_tokens: 2048,
      temperature: 0.7,
      top_p: 0.9,
      top_k: 50,
      repetition_penalty: 1.1
    })
    
    // 计算属性
    const modelName = computed(() => {
      if (!model.value) return '未知模型'
      return model.value.name
    })
    
    const shareUrl = computed(() => {
      if (!shareEnabled.value) return ''
      const baseUrl = window.location.origin
      return `${baseUrl}/shared/${taskId}`
    })
    
    // 加载任务详情
    const loadTask = async () => {
      try {
        loading.value = true
        const response = await inference.getTask(taskId)
        task.value = response.data
        
        // 如果存在任务，更新表单数据
        if (task.value) {
          // 更新模型信息
          loadModel(task.value.model_id)
          
          // 更新参数表单
          params.max_tokens = task.value.max_tokens
          params.temperature = task.value.temperature
          params.top_p = task.value.top_p
          params.top_k = task.value.top_k
          params.repetition_penalty = task.value.repetition_penalty
          
          // 更新共享设置
          console.log('从服务器获取共享设置:', {
            share_enabled: task.value.share_enabled,
            display_name: task.value.display_name
          })
          shareEnabled.value = task.value.share_enabled
          displayName.value = task.value.display_name || task.value.name
        }
      } catch (error) {
        console.error('加载推理任务失败:', error)
        showToast('加载推理任务失败: ' + (error.response?.data?.detail || error.message), 'error')
        task.value = null
      } finally {
        loading.value = false
      }
    }
    
    // 加载模型信息
    const loadModel = async (modelId) => {
      try {
        const response = await apiClient.get(`/api/resources/${modelId}`)
        model.value = response.data
      } catch (error) {
        console.error('加载模型信息失败:', error)
        model.value = null
      }
    }
    
    // 刷新任务状态
    const refreshTask = async () => {
      if (loading.value) return
      
      try {
        const response = await inference.getTask(taskId)
        task.value = response.data
      } catch (error) {
        console.error('刷新任务状态失败:', error)
      }
    }
    
    // 启动任务
    const startTask = async () => {
      try {
        showToast('正在启动推理任务...', 'info')
        await inference.startTask(taskId)
        showToast('推理任务启动成功', 'success')
        await refreshTask()
      } catch (error) {
        console.error('启动推理任务失败:', error)
        showToast('启动推理任务失败: ' + (error.response?.data?.detail || error.message), 'error')
      }
    }
    
    // 停止任务
    const stopTask = async () => {
      try {
        showToast('正在停止推理任务...', 'info')
        await inference.stopTask(taskId)
        showToast('推理任务已停止', 'success')
        await refreshTask()
      } catch (error) {
        console.error('停止推理任务失败:', error)
        showToast('停止推理任务失败: ' + (error.response?.data?.detail || error.message), 'error')
      }
    }
    
    // 打开删除确认对话框
    const confirmDelete = () => {
      showDeleteModal.value = true
    }
    
    // 删除任务
    const deleteTask = async () => {
      try {
        await inference.deleteTask(taskId)
        showToast('推理任务已删除', 'success')
        showDeleteModal.value = false
        router.push('/inference')
      } catch (error) {
        console.error('删除推理任务失败:', error)
        showToast('删除推理任务失败: ' + (error.response?.data?.detail || error.message), 'error')
      }
    }
    
    // 更新参数
    const updateParams = async () => {
      if (!task.value || !task.value.id) return;
      
      try {
        isUpdating.value = true;
        // 构建参数对象
        const paramsToUpdate = {
          max_tokens: parseInt(params.max_tokens),
          temperature: parseFloat(params.temperature),
          top_p: parseFloat(params.top_p),
          top_k: parseInt(params.top_k),
          repetition_penalty: parseFloat(params.repetition_penalty)
        };
        
        // 调用API更新参数
        await inference.updateParams(task.value.id, paramsToUpdate);
        
        // 更新成功
        showToast('参数更新成功', 'success');
        
        // 重新加载任务信息以获取最新状态
        await loadTask();
      } catch (error) {
        // 错误处理
        showToast('更新参数失败: ' + (error.response?.data?.detail || error.message), 'error');
        console.error('更新参数失败:', error);
      } finally {
        isUpdating.value = false;
      }
    };
    
    // 更新共享设置
    const updateShareSettings = async () => {
      if (!task.value) return
      
      try {
        isUpdating.value = true
        console.log('开始更新共享设置:', {
          taskId,
          shareEnabled: shareEnabled.value, 
          displayName: displayName.value || task.value.name
        })
        
        // 使用专门的共享切换API
        const response = await inference.toggleShareStatus(
          taskId, 
          shareEnabled.value, 
          displayName.value || task.value.name
        )
        
        console.log('共享设置API响应:', response.data)
        showToast('共享设置已更新', 'success')
        
        // 刷新任务信息
        await loadTask()
        console.log('刷新后的任务数据:', task.value)
      } catch (error) {
        console.error('更新共享设置失败:', error)
        console.error('详细错误信息:', {
          status: error.response?.status,
          data: error.response?.data,
          message: error.message
        })
        showToast('更新共享设置失败: ' + (error.response?.data?.detail || error.message), 'error')
      } finally {
        isUpdating.value = false
      }
    }
    
    // 复制共享链接
    const copyShareUrl = () => {
      if (!shareUrlInput.value) return
      
      shareUrlInput.value.select()
      document.execCommand('copy')
      
      showToast('共享链接已复制到剪贴板', 'success')
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
    const getStatusText = (status) => {
      const statusMap = {
        'CREATING': '创建中',
        'RUNNING': '运行中',
        'STOPPED': '已停止',
        'FAILED': '失败'
      }
      return statusMap[status] || status
    }
    
    // 生命周期钩子
    onMounted(async () => {
      await loadTask()
      
      // 设置定时刷新
      refreshTimer = setInterval(refreshTask, 5000)
    })
    
    onUnmounted(() => {
      // 清除定时器
      if (refreshTimer) {
        clearInterval(refreshTimer)
      }
    })
    
    return {
      taskId,
      task,
      model,
      loading,
      isUpdating,
      showDeleteModal,
      showParamsModal,
      params,
      modelName,
      shareEnabled,
      displayName,
      shareUrl,
      shareUrlInput,
      updateParams,
      startTask,
      stopTask,
      confirmDelete,
      deleteTask,
      updateShareSettings,
      copyShareUrl,
      formatMemory,
      formatDateTime,
      getStatusText
    }
  }
}
</script>

<style scoped>
.inference-detail-page {
  max-width: 1000px;
  margin: 0 auto;
  padding-bottom: 40px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 16px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.back-link {
  display: flex;
  align-items: center;
  color: var(--primary);
  text-decoration: none;
}

.page-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.task-status {
  font-size: 0.9em;
  padding: 4px 8px;
  border-radius: 4px;
  background-color: var(--surface-color);
}

.task-status.running {
  background-color: #4CAF50;
  color: white;
}

.task-status.creating {
  background-color: #2196F3;
  color: white;
}

.task-status.stopped {
  background-color: #FF9800;
  color: white;
}

.task-status.failed {
  background-color: #F44336;
  color: white;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 0;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(0, 0, 0, 0.1);
  border-radius: 50%;
  border-top-color: var(--primary);
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-container {
  text-align: center;
  padding: 48px 0;
}

.error-icon {
  font-size: 48px;
  color: #F44336;
  margin-bottom: 16px;
}

.section {
  background-color: var(--surface-color);
  border-radius: 8px;
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.section h2 {
  margin-top: 0;
  margin-bottom: 20px;
  font-size: 18px;
  font-weight: 500;
  color: var(--text-primary);
  padding-bottom: 12px;
  border-bottom: 1px solid var(--divider-color);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.info-item {
  margin-bottom: 8px;
}

.info-label {
  font-size: 0.9em;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.info-value {
  font-weight: 500;
  color: var(--text-primary);
}

.info-value.code {
  font-family: monospace;
  background-color: var(--surface-variant-color);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.9em;
  word-break: break-all;
}

.status {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.9em;
}

.error-message {
  margin-top: 24px;
  padding: 16px;
  background-color: #FFEBEE;
  border-radius: 4px;
  border-left: 4px solid #F44336;
}

.error-message h3 {
  margin-top: 0;
  margin-bottom: 8px;
  color: #D32F2F;
  font-size: 16px;
}

.error-content {
  white-space: pre-wrap;
  font-family: monospace;
  font-size: 0.9em;
  color: #D32F2F;
}

.params-update {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid var(--divider-color);
}

.params-update h3 {
  margin-top: 0;
  margin-bottom: 16px;
  font-size: 16px;
  font-weight: 500;
}

.params-form {
  background-color: var(--surface-variant-color);
  padding: 16px;
  border-radius: 8px;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.form-group {
  margin-bottom: 12px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-size: 0.9em;
  color: var(--text-primary);
}

.form-group input {
  width: 100%;
  padding: 8px;
  border: 1px solid var(--divider-color);
  border-radius: 4px;
  background-color: var(--background-color);
  color: var(--text-primary);
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
  max-width: 500px;
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

.btn-primary {
  background-color: var(--primary);
  color: var(--on-primary);
}

.btn-secondary {
  background-color: var(--surface-variant-color);
  color: var(--on-surface-variant);
}

.btn-success {
  background-color: #4CAF50;
  color: white;
}

.btn-warning {
  background-color: #FF9800;
  color: white;
}

.btn-danger {
  background-color: #F44336;
  color: white;
}

.btn[disabled] {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 响应式调整 */
@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .info-grid {
    grid-template-columns: 1fr;
  }
  
  .form-row {
    grid-template-columns: 1fr;
  }
}
</style> 