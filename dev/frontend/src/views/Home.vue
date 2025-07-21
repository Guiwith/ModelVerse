<template>
  <div class="home-page">
    <!-- 添加动态背景 -->
  
    
    <div class="page-header">
      <h1>欢迎{{ username ? '，' + username : '' }}</h1>
      <p class="subtitle">您的AI模型管理中心</p>
    </div>

    <div class="grid">
      <!-- 个人信息卡片 -->
      <div class="grid-item user-profile">
        <div class="card">
          <div class="profile-header">
            <span class="material-icons profile-avatar">account_circle</span>
            <div class="profile-info">
              <h2>{{ username }}</h2>
              <p>{{ email || '未设置邮箱' }}</p>
              <span class="badge" :class="isAdmin ? 'badge-admin' : 'badge-user'">
                {{ isAdmin ? '管理员' : '普通用户' }}
              </span>
            </div>
          </div>

          <div class="profile-actions">
            <router-link to="/profile" class="btn btn-primary">
              <span class="material-icons">edit</span>
              编辑资料
            </router-link>
          </div>
        </div>
      </div>

      <!-- 模型资源卡片 -->
      <div class="grid-item models-overview">
        <div class="card">
          <div class="card-header">
            <h2>模型资源</h2>
            <router-link to="/resources" class="btn-icon" title="查看全部模型">
              <span class="material-icons">arrow_forward</span>
            </router-link>
          </div>

          <div v-if="modelsLoading" class="loading-container">
            <div class="loader"></div>
            <p>加载中...</p>
          </div>

          <div v-else-if="modelsError" class="alert alert-error">
            <span class="material-icons">error</span>
            <p>{{ modelsError }}</p>
          </div>

          <div v-else-if="models.length === 0" class="empty-state">
            <span class="material-icons">model_training</span>
            <p>暂无模型</p>
            
          </div>

          <div v-else class="models-list">
            <div v-for="model in limitedModels" :key="model.id" class="model-item">
              <div class="model-item-header">
                <span class="model-name">{{ model.name }}</span>
                <span class="model-badge" :class="statusClass(model.status)">{{ statusText(model.status) }}</span>
              </div>
              <p class="model-repo">{{ model.repo_id }}</p>
              
              <div v-if="model.status === 'DOWNLOADING'" class="progress-bar">
                <div class="progress-fill" :style="{width: `${model.progress * 100}%`}"></div>
                <span class="progress-text">{{ (model.progress * 100).toFixed(0) }}%</span>
              </div>
            </div>
            
            <div v-if="models.length > 3" class="models-more">
              <router-link to="/resources" class="btn btn-text">
                查看全部 {{ models.length }} 个模型
              </router-link>
            </div>
          </div>
        </div>
      </div>

      <!-- 训练任务卡片 -->
      <div class="grid-item training-overview">
        <div class="card">
          <div class="card-header">
            <h2>训练任务</h2>
            <router-link to="/training" class="btn-icon" title="查看全部训练任务">
              <span class="material-icons">arrow_forward</span>
            </router-link>
          </div>

          <div v-if="tasksLoading" class="loading-container">
            <div class="loader"></div>
            <p>加载中...</p>
          </div>

          <div v-else-if="tasksError" class="alert alert-error">
            <span class="material-icons">error</span>
            <p>{{ tasksError }}</p>
          </div>

          <div v-else-if="tasks.length === 0" class="empty-state">
            <span class="material-icons">psychology</span>
            <p>暂无训练任务</p>
          </div>

          <div v-else class="tasks-list">
            <div v-for="task in limitedTasks" :key="task.id" class="task-item">
              <div class="task-item-header">
                <span class="task-name">{{ task.name }}</span>
                <span class="task-badge" :class="trainingStatusClass(task.status)">{{ trainingStatusText(task.status) }}</span>
              </div>
              
              <div class="task-details">
                <div class="task-detail">
                  <span class="material-icons icon-sm">model_training</span>
                  <span>{{ getResourceName(task.base_model_id) }}</span>
                </div>
                <div class="task-detail">
                  <span class="material-icons icon-sm">dataset</span>
                  <span>{{ getResourceName(task.dataset_id) }}</span>
                </div>
              </div>
              
              <div v-if="task.status === 'RUNNING'" class="progress-bar">
                <div class="progress-fill" :style="{width: `${task.progress * 100}%`}"></div>
                <span class="progress-text">{{ (task.progress * 100).toFixed(0) }}%</span>
              </div>
            </div>
            
            <div v-if="tasks.length > 3" class="tasks-more">
              <router-link to="/training" class="btn btn-text">
                查看全部 {{ tasks.length }} 个训练任务
              </router-link>
            </div>
          </div>
        </div>
      </div>

      <!-- 快速操作卡片 -->
      <div class="grid-item quick-actions">
        <div class="card">
          <div class="card-header">
            <h2>快速操作</h2>
          </div>
          <div class="actions-grid">
            <router-link to="/resources" class="action-item">
              <span class="material-icons">storage</span>
              <span>模型管理</span>
            </router-link>
            <router-link to="/resources?type=DATASET" class="action-item">
              <span class="material-icons">dataset</span>
              <span>数据集管理</span>
            </router-link>
            <router-link to="/training" class="action-item">
              <span class="material-icons">psychology</span>
              <span>训练任务</span>
            </router-link>
            <router-link to="/profile" class="action-item">
              <span class="material-icons">settings</span>
              <span>设置</span>
            </router-link>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import * as api from '../api/client'

export default {
  name: 'Home',
  setup() {
    const username = ref('')
    const email = ref('')
    const isAdmin = ref(false)
    
    const models = ref([])
    const modelsLoading = ref(true)
    const modelsError = ref(null)
    
    // 训练任务相关
    const tasks = ref([])
    const tasksLoading = ref(true)
    const tasksError = ref(null)
    const allResources = ref({})

    // 获取用户数据
    onMounted(() => {
      // 从本地存储获取用户信息
      const userInfo = localStorage.getItem('user_info')
      if (userInfo) {
        try {
          const user = JSON.parse(userInfo)
          username.value = user.username
          email.value = user.email || ''
          isAdmin.value = user.is_admin === true
        } catch (e) {
          console.error('解析用户信息失败:', e)
        }
      }

      // 加载模型列表
      loadModels()
      
      // 加载训练任务
      loadTasks()
      
      // 加载所有资源以便显示名称
      loadAllResources()
      
      // 添加主题变化监听器
      const darkThemeObserver = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
          if (mutation.attributeName === 'class') {
            const isDarkTheme = document.documentElement.classList.contains('dark-theme')
            const cards = document.querySelectorAll('.card')
            cards.forEach(card => {
              if (isDarkTheme) {
                card.style.backgroundColor = 'rgba(48, 48, 48, 0.9)'
              } else {
                card.style.backgroundColor = 'rgba(255, 255, 255, 0.9)'
              }
            })
          }
        })
      })
      
      darkThemeObserver.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['class']
      })
      
      // 初始设置
      const isDarkTheme = document.documentElement.classList.contains('dark-theme')
      const cards = document.querySelectorAll('.card')
      cards.forEach(card => {
        if (isDarkTheme) {
          card.style.backgroundColor = 'rgba(48, 48, 48, 0.9)'
        } else {
          card.style.backgroundColor = 'rgba(255, 255, 255, 0.9)'
        }
      })
    })

    // 加载模型列表
    const loadModels = async () => {
      modelsLoading.value = true
      modelsError.value = null

      try {
        const response = await api.apiClient.get('/api/resources')
        models.value = response.data.filter(resource => resource.resource_type === 'MODEL')
      } catch (err) {
        console.error('加载模型失败:', err)
        modelsError.value = '加载失败'
      } finally {
        modelsLoading.value = false
      }
    }
    
    // 加载训练任务
    const loadTasks = async () => {
      tasksLoading.value = true
      tasksError.value = null

      try {
        const response = await api.training.getTasks()
        tasks.value = response.data
      } catch (err) {
        console.error('加载训练任务失败:', err)
        tasksError.value = '加载失败'
      } finally {
        tasksLoading.value = false
      }
    }
    
    // 加载所有资源
    const loadAllResources = async () => {
      try {
        const response = await api.apiClient.get('/api/resources')
        // 创建资源ID到名称的映射
        const resourceMap = {}
        response.data.forEach(resource => {
          resourceMap[resource.id] = resource.name
        })
        allResources.value = resourceMap
      } catch (err) {
        console.error('加载资源失败:', err)
      }
    }

    // 只显示最近的3个模型
    const limitedModels = computed(() => {
      return models.value.slice(0, 3)
    })
    
    // 只显示最近的3个训练任务
    const limitedTasks = computed(() => {
      return tasks.value.slice(0, 3)
    })
    
    // 获取资源名称
    const getResourceName = (resourceId) => {
      return allResources.value[resourceId] || `资源#${resourceId}`
    }
    
    // 跳转到搜索页面
    const goToSearch = () => {
      // 可以在这里实现搜索功能或跳转到搜索页面
      alert('搜索功能尚未实现')
    }
    
    // 状态相关工具函数
    const statusText = (status) => {
      const map = {
        'PENDING': '等待下载',
        'DOWNLOADING': '下载中',
        'COMPLETED': '已完成',
        'FAILED': '下载失败',
        'CANCELLED': '已取消'
      }
      return map[status] || status
    }
    
    const statusClass = (status) => {
      const map = {
        'PENDING': 'status-pending',
        'DOWNLOADING': 'status-downloading',
        'COMPLETED': 'status-completed',
        'FAILED': 'status-failed',
        'CANCELLED': 'status-cancelled'
      }
      return map[status] || ''
    }
    
    // 训练任务状态
    const trainingStatusText = (status) => {
      const map = {
        'PENDING': '等待中',
        'RUNNING': '训练中',
        'COMPLETED': '已完成',
        'FAILED': '失败',
        'STOPPED': '已停止'
      }
      return map[status] || status
    }
    
    const trainingStatusClass = (status) => {
      const map = {
        'PENDING': 'status-pending',
        'RUNNING': 'status-downloading', // 复用下载中的样式
        'COMPLETED': 'status-completed',
        'FAILED': 'status-failed',
        'STOPPED': 'status-cancelled'  // 复用已取消的样式
      }
      return map[status] || ''
    }

    return {
      username,
      email,
      isAdmin,
      models,
      modelsLoading,
      modelsError,
      limitedModels,
      tasks,
      tasksLoading,
      tasksError,
      limitedTasks,
      loadModels,
      loadTasks,
      getResourceName,
      goToSearch,
      statusText,
      statusClass,
      trainingStatusText,
      trainingStatusClass
    }
  }
}
</script>

<style scoped>
.home-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  position: relative;
  z-index: 2;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 28px;
  margin-bottom: 8px;
}

.subtitle {
  color: var(--text-secondary);
  font-size: 16px;
}

/* 网格布局 */
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: auto auto auto;
  gap: 24px;
}

.grid-item.user-profile {
  grid-column: 1;
  grid-row: 1;
}

.grid-item.models-overview {
  grid-column: 2;
  grid-row: 1;
}

.grid-item.training-overview {
  grid-column: 1;
  grid-row: 2;
}

.grid-item.quick-actions {
  grid-column: 2;
  grid-row: 2;
}

/* 卡片样式 */
.card {
  backdrop-filter: blur(5px);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 20px;
  height: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.card-header h2 {
  font-size: 20px;
  margin: 0;
}

/* 个人资料卡片 */
.profile-header {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
}

.profile-avatar {
  font-size: 60px;
  color: var(--primary);
  margin-right: 16px;
}

.profile-info h2 {
  margin: 0 0 4px 0;
  font-size: 20px;
}

.profile-info p {
  margin: 0 0 8px 0;
  color: var(--text-secondary);
}

.badge {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 16px;
  font-size: 12px;
  font-weight: 500;
}

.badge-admin {
  background-color: var(--primary-light);
  color: var(--primary);
}

.badge-user {
  background-color: var(--bg-card-secondary);
  color: var(--text-secondary);
}

.profile-actions {
  display: flex;
  justify-content: flex-end;
}

/* 模型列表和训练任务列表通用样式 */
.models-list, .tasks-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.model-item, .task-item {
  padding: 12px;
  background-color: var(--bg-card-secondary);
  border-radius: 6px;
  transition: transform 0.2s, background-color 0.2s;
}

.model-item:hover, .task-item:hover {
  transform: translateY(-2px);
  background-color: var(--bg-hover);
}

.model-item-header, .task-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.model-name, .task-name {
  font-weight: 500;
}

.model-badge, .task-badge {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}

.status-pending { background-color: #fff8e1; color: #ff9800; }
.status-downloading { background-color: #e3f2fd; color: #2196f3; }
.status-completed { background-color: #e8f5e9; color: #4caf50; }
.status-failed { background-color: #ffebee; color: #f44336; }
.status-cancelled { background-color: #f5f5f5; color: #9e9e9e; }

.model-repo {
  font-family: monospace;
  font-size: 12px;
  color: var(--text-secondary);
  margin: 4px 0 8px 0;
}

.task-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 8px 0;
}

.task-detail {
  display: flex;
  align-items: center;
  font-size: 12px;
  color: var(--text-secondary);
}

.icon-sm {
  font-size: 16px;
  margin-right: 4px;
}

.progress-bar {
  height: 6px;
  background-color: rgba(0,0,0,0.1);
  border-radius: 3px;
  overflow: hidden;
  position: relative;
  margin-top: 8px;
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

.models-more, .tasks-more {
  display: flex;
  justify-content: center;
  margin-top: 12px;
}

.btn-text {
  background: none;
  border: none;
  color: var(--primary);
  text-decoration: underline;
  cursor: pointer;
  padding: 4px 8px;
}

/* 快速操作 */
.actions-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  grid-template-rows: repeat(2, 1fr);
  gap: 16px;
}

.action-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px;
  background-color: var(--bg-card-secondary);
  border-radius: 8px;
  text-decoration: none;
  color: var(--text-primary);
  transition: transform 0.2s, background-color 0.2s;
}

.action-item:hover {
  transform: translateY(-4px);
  background-color: var(--bg-hover);
}

.action-item .material-icons {
  font-size: 32px;
  margin-bottom: 8px;
  color: var(--primary);
}

/* 加载和空状态 */
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px 0;
}

.loader {
  border: 3px solid var(--bg-card-secondary);
  border-top: 3px solid var(--primary);
  border-radius: 50%;
  width: 24px;
  height: 24px;
  animation: spin 1s linear infinite;
  margin-bottom: 12px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 0;
  color: var(--text-secondary);
}

.empty-state .material-icons {
  font-size: 48px;
  margin-bottom: 16px;
  color: var(--text-tertiary);
}

.empty-state p {
  margin-bottom: 16px;
}

.alert {
  display: flex;
  align-items: center;
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 16px;
}

.alert-error {
  background-color: #ffebee;
  color: #f44336;
}

.alert .material-icons {
  margin-right: 8px;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 8px 16px;
  border-radius: 4px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  text-decoration: none;
}

.btn-primary {
  background-color: var(--primary);
  color: white;
}

.btn-sm {
  padding: 4px 8px;
  font-size: 12px;
}

.btn-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: transparent;
  color: var(--text-secondary);
  transition: background-color 0.2s;
  text-decoration: none;
}

.btn-icon:hover {
  background-color: var(--bg-hover);
  color: var(--primary);
}

/* 响应式布局 */
@media (max-width: 768px) {
  .grid {
    grid-template-columns: 1fr;
  }
  
  .grid-item.user-profile,
  .grid-item.models-overview,
  .grid-item.training-overview,
  .grid-item.quick-actions {
    grid-column: 1;
  }
  
  .grid-item.user-profile {
    grid-row: 1;
  }
  
  .grid-item.models-overview {
    grid-row: 2;
  }
  
  .grid-item.training-overview {
    grid-row: 3;
  }
  
  .grid-item.quick-actions {
    grid-row: 4;
  }
  
  .actions-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* 背景动画效果 */
.animated-bg {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 1;
  overflow: hidden;
}

.bg-circle {
  position: absolute;
  border-radius: 50%;
  background: linear-gradient(45deg, var(--primary), var(--primary-dark));
  opacity: 0.15;
  filter: blur(40px);
}

.bg-circle:nth-child(1) {
  width: 800px;
  height: 800px;
  top: -20%;
  right: -20%;
  animation: float-circle1 60s infinite linear;
}

.bg-circle:nth-child(2) {
  width: 600px;
  height: 600px;
  bottom: -20%;
  left: -10%;
  animation: float-circle2 75s infinite linear;
}

.bg-circle:nth-child(3) {
  width: 500px;
  height: 500px;
  top: 40%;
  left: 60%;
  animation: float-circle3 90s infinite linear;
}

@keyframes float-circle1 {
  0% { transform: translate(0, 0); }
  25% { transform: translate(-10%, 15%); }
  50% { transform: translate(5%, 25%); }
  75% { transform: translate(15%, 5%); }
  100% { transform: translate(0, 0); }
}

@keyframes float-circle2 {
  0% { transform: translate(0, 0); }
  25% { transform: translate(15%, -10%); }
  50% { transform: translate(5%, -25%); }
  75% { transform: translate(-10%, -15%); }
  100% { transform: translate(0, 0); }
}

@keyframes float-circle3 {
  0% { transform: translate(0, 0) scale(1); }
  20% { transform: translate(-15%, 10%) scale(1.1); }
  40% { transform: translate(-20%, -15%) scale(0.9); }
  60% { transform: translate(10%, -20%) scale(1.2); }
  80% { transform: translate(20%, 15%) scale(0.95); }
  100% { transform: translate(0, 0) scale(1); }
}
</style> 