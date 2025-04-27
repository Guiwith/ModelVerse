<template>
  <div class="shared-chat-list-page">
    <div class="page-header">
      <h1>公开聊天模型</h1>
      <p class="description">以下是可以直接使用的聊天机器人模型，无需登录即可使用</p>
    </div>
    
    <div v-if="loading" class="loading-container">
      <div class="loading-spinner"></div>
      <p>正在加载可用的聊天模型...</p>
    </div>
    
    <div v-else-if="error" class="error-container">
      <div class="error-icon">
        <span class="material-icons">error_outline</span>
      </div>
      <h2>加载失败</h2>
      <p>{{ errorMessage }}</p>
      <button @click="loadTasks" class="btn btn-primary">
        <span class="material-icons">refresh</span>
        重试
      </button>
    </div>
    
    <div v-else-if="tasks.length === 0" class="empty-container">
      <div class="empty-icon">
        <span class="material-icons">chat_bubble_outline</span>
      </div>
      <h2>暂无可用的聊天模型</h2>
      <p>当前没有已共享的聊天模型可供使用</p>
      <button @click="loadTasks" class="btn btn-secondary">
        <span class="material-icons">refresh</span>
        刷新
      </button>
    </div>
    
    <div v-else class="tasks-container">
      <div class="refresh-container">
        <button @click="loadTasks" class="btn btn-secondary refresh-btn">
          <span class="material-icons">refresh</span>
          刷新
        </button>
      </div>
      <div class="task-cards">
        <div 
          v-for="task in tasks" 
          :key="task.id" 
          class="task-card"
          @click="goToChat(task.id)"
        >
          <div class="card-header">
            <div class="model-icon">
              <span class="material-icons">smart_toy</span>
            </div>
            <div class="model-info">
              <h2 class="model-name">{{ task.display_name }}</h2>
              <span class="status-badge running">
                <span class="status-dot"></span>
                运行中
              </span>
            </div>
          </div>
          
          <div class="card-footer">
            <button class="btn btn-primary">
              <span class="material-icons">chat</span>
              开始对话
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { sharedApiClient, sharedInference } from '../api/client'

export default {
  name: 'SharedChatList',
  setup() {
    const router = useRouter()
    
    // 数据
    const tasks = ref([])
    const loading = ref(true)
    const error = ref(false)
    const errorMessage = ref('')
    
    // 刷新定时器
    let refreshTimer = null
    
    // 加载共享任务列表
    const loadTasks = async () => {
      try {
        loading.value = true
        error.value = false
        errorMessage.value = ''
        
        console.log('正在加载共享聊天模型...')
        const response = await sharedInference.getTasks()
        
        if (response.data && Array.isArray(response.data)) {
          tasks.value = response.data
          console.log(`加载了 ${tasks.value.length} 个共享聊天模型`)
        } else {
          console.error('API返回了意外格式的数据:', response.data)
          throw new Error('服务器返回了意外的数据格式')
        }
      } catch (error) {
        console.error('加载共享聊天模型失败:', error)
        tasks.value = []
        error.value = true
        errorMessage.value = error.message || '无法连接到服务器，请稍后重试'
      } finally {
        loading.value = false
      }
    }
    
    // 定时刷新任务列表
    const startRefreshTimer = () => {
      stopRefreshTimer() // 先清除可能存在的定时器
      refreshTimer = setInterval(loadTasks, 60000) // 每60秒刷新一次
      console.log('已启动自动刷新')
    }
    
    // 停止刷新
    const stopRefreshTimer = () => {
      if (refreshTimer) {
        clearInterval(refreshTimer)
        refreshTimer = null
        console.log('已停止自动刷新')
      }
    }
    
    // 跳转到聊天页面
    const goToChat = (id) => {
      router.push(`/shared/${id}`)
    }
    
    // 生命周期钩子
    onMounted(() => {
      loadTasks()
      startRefreshTimer()
    })
    
    onBeforeUnmount(() => {
      stopRefreshTimer()
    })
    
    return {
      tasks,
      loading,
      error,
      errorMessage,
      loadTasks,
      goToChat
    }
  }
}
</script>

<style scoped>
.shared-chat-list-page {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 2rem;
  text-align: center;
}

.page-header h1 {
  font-size: 2.5rem;
  margin-bottom: 1rem;
  color: var(--text-primary);
}

.description {
  font-size: 1.1rem;
  color: var(--text-secondary);
  max-width: 800px;
  margin: 0 auto;
}

.loading-container,
.empty-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  text-align: center;
}

.loading-spinner {
  width: 50px;
  height: 50px;
  border: 5px solid var(--divider-color);
  border-radius: 50%;
  border-top: 5px solid var(--primary);
  animation: spin 1s linear infinite;
  margin-bottom: 1rem;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.empty-icon {
  font-size: 5rem;
  color: var(--text-disabled);
  margin-bottom: 1rem;
}

.empty-icon .material-icons {
  font-size: 5rem;
}

.empty-container h2 {
  font-size: 1.8rem;
  margin-bottom: 0.5rem;
  color: var(--text-primary);
}

.empty-container p {
  font-size: 1.1rem;
  color: var(--text-secondary);
}

.task-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 2rem;
}

.task-card {
  background-color: var(--surface-color);
  border-radius: 10px;
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
  padding: 1.5rem;
  transition: transform 0.3s, box-shadow 0.3s;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 180px;
}

.task-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
}

.card-header {
  display: flex;
  align-items: flex-start;
  margin-bottom: 1.5rem;
}

.model-icon {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  background-color: var(--primary-light);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 1rem;
}

.model-icon .material-icons {
  font-size: 28px;
  color: var(--primary);
}

.model-info {
  flex: 1;
}

.model-name {
  font-size: 1.4rem;
  margin-bottom: 0.5rem;
  color: var(--text-primary);
  line-height: 1.3;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.5rem;
  border-radius: 50px;
  font-size: 0.8rem;
  font-weight: 500;
}

.status-badge.running {
  background-color: var(--success-light);
  color: var(--success);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 5px;
  background-color: var(--success);
  position: relative;
}

.status-badge.running .status-dot::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background-color: var(--success);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% {
    transform: scale(1);
    opacity: 1;
  }
  70% {
    transform: scale(2);
    opacity: 0;
  }
  100% {
    transform: scale(1);
    opacity: 0;
  }
}

.card-footer {
  display: flex;
  justify-content: flex-end;
}

.btn {
  display: inline-flex;
  align-items: center;
  padding: 0.5rem 1rem;
  border-radius: 5px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: background-color 0.3s;
}

.btn-primary {
  background-color: var(--primary);
  color: var(--on-primary);
}

.btn-primary:hover {
  background-color: var(--primary-dark);
}

.btn-secondary {
  background-color: var(--surface-variant-color);
  color: var(--on-surface-variant);
}

.btn-secondary:hover {
  background-color: var(--hover-color);
}

.btn .material-icons {
  font-size: 18px;
  margin-right: 5px;
}

.refresh-container {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 1rem;
}

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  text-align: center;
}

.error-icon {
  font-size: 5rem;
  color: var(--error);
  margin-bottom: 1rem;
}

.error-icon .material-icons {
  font-size: 5rem;
}
</style> 