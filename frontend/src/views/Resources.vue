<template>
  <div class="resource-page">
    <div class="page-header">
      <h1>模型与数据集资源</h1>
      <p class="subtitle">管理您的模型和数据集</p>
    </div>

    <div class="resource-actions">
      <button class="btn btn-primary" @click="showAddDialog = true">
        <span class="material-icons">add</span> 添加新资源
      </button>
      <!-- <button class="btn btn-secondary" @click="scanLocalResources">
        <span class="material-icons">search</span> 扫描本地资源
      </button> -->
      <div class="filter-group">
        <label for="resourceType">资源类型：</label>
        <select id="resourceType" v-model="filter.type" class="form-control">
          <option value="all">全部</option>
          <option value="MODEL">模型</option>
          <option value="DATASET">数据集</option>
        </select>
      </div>
      <div class="filter-group">
        <label for="statusFilter">状态：</label>
        <select id="statusFilter" v-model="filter.status" class="form-control">
          <option value="all">全部</option>
          <option value="PENDING">等待下载</option>
          <option value="DOWNLOADING">下载中</option>
          <option value="COMPLETED">已完成</option>
          <option value="FAILED">失败</option>
        </select>
      </div>
    </div>

    <div v-if="loading" class="loading-container">
      <div class="loader"></div>
      <p>加载资源列表...</p>
    </div>

    <div v-else-if="error" class="error-message">
      <span class="material-icons">error</span>
      <p>{{ error }}</p>
      <button class="btn btn-outline" @click="loadResources">重试</button>
    </div>

    <div v-else-if="filteredResources.length === 0" class="empty-state">
      <span class="material-icons">inventory_2</span>
      <h3>暂无资源</h3>
      <p>您还没有添加任何{{ filter.type === 'MODEL' ? '模型' : filter.type === 'DATASET' ? '数据集' : '模型或数据集' }}资源</p>
      <button class="btn btn-primary" @click="showAddDialog = true">添加资源</button>
    </div>

    <div v-else class="resources-grid">
      <div v-for="resource in filteredResources" :key="resource.id" class="resource-card">
        <div class="resource-header">
          <span class="resource-type-badge" :class="{'model': resource.resource_type === 'MODEL', 'dataset': resource.resource_type === 'DATASET'}">
            {{ resource.resource_type === 'MODEL' ? '模型' : '数据集' }}
          </span>
          <h3 class="resource-name">{{ resource.name }}</h3>
        </div>
        
        <div class="resource-info">
          <p class="resource-repo">{{ resource.repo_id }}</p>
          <p class="resource-description">{{ resource.description || '暂无描述' }}</p>
        </div>
        
        <div class="resource-status">
          <div v-if="resource.status === 'DOWNLOADING'" class="progress-bar">
            <div class="progress-fill" :style="{width: `${resource.progress}%`}"></div>
          </div>
          <div class="status-label" :class="statusClass(resource.status)">
            <span class="material-icons">{{ statusIcon(resource.status) }}</span>
            <span>{{ statusText(resource.status) }}</span>
            <span v-if="resource.status === 'DOWNLOADING'">({{ resource.progress.toFixed(0) }}%)</span>
          </div>
        </div>
        
        <div class="resource-size" v-if="resource.size_mb">
          <span class="material-icons">sd_storage</span>
          <span>{{ formatSize(resource.size_mb) }}</span>
        </div>
        
        <div class="resource-actions">
          <button v-if="resource.status === 'PENDING'" 
                  class="btn btn-primary" 
                  @click="downloadResource(resource.id)">
            <span class="material-icons">download</span> 下载
          </button>
          <button v-if="resource.status === 'DOWNLOADING'" 
                  class="btn btn-outline" 
                  @click="cancelDownload(resource.id)">
            <span class="material-icons">cancel</span> 取消
          </button>
          <button v-if="resource.status === 'COMPLETED'" 
                  class="btn btn-outline" 
                  @click="viewDetails(resource.id)">
            <span class="material-icons">info</span> 详情
          </button>
          <button v-if="resource.status === 'FAILED'" 
                  class="btn btn-outline" 
                  @click="retryDownload(resource.id)">
            <span class="material-icons">restart_alt</span> 重试
          </button>
          <button class="btn btn-danger" @click="deleteResource(resource.id)">
            <span class="material-icons">delete</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 添加资源对话框 -->
    <div v-if="showAddDialog" class="modal-overlay">
      <div class="modal-dialog">
        <div class="modal-header">
          <h2>添加新资源</h2>
          <button class="btn-close" @click="showAddDialog = false">
            <span class="material-icons">close</span>
          </button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label for="resourceName">资源名称</label>
            <input type="text" id="resourceName" v-model="newResource.name" class="form-control" required>
          </div>
          <div class="form-group">
            <label for="resourceRepo">仓库ID(目前只提供huggingface下载源)</label>
            <input type="text" id="resourceRepo" v-model="newResource.repo_id" class="form-control" 
                   placeholder="例如：facebook/opt-350m" required>
          </div>
          <div class="form-group">
            <label for="resourceDescription">描述</label>
            <textarea id="resourceDescription" v-model="newResource.description" class="form-control" rows="3"></textarea>
          </div>
          <div class="form-group">
            <label>资源类型</label>
            <div class="radio-group">
              <label class="radio-label">
                <input type="radio" v-model="newResource.resource_type" value="MODEL">
                <span>模型</span>
              </label>
              <label class="radio-label">
                <input type="radio" v-model="newResource.resource_type" value="DATASET">
                <span>数据集</span>
              </label>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="showAddDialog = false">取消</button>
          <button class="btn btn-primary" @click="addResource" :disabled="!isFormValid">添加</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import * as api from '../api/client'
import { useAuth } from '../composables/auth'
import { useToast } from '../composables/toast'

export default {
  name: 'Resources',
  components: {
    // ... existing code ...
  },
  setup() {
    const resources_data = ref([])
    const loading = ref(true)
    const error = ref(null)
    const showAddDialog = ref(false)
    const ws = ref(null)
    const refreshTimer = ref(null)
    const wsReconnectTimer = ref(null)
    
    // 用于记录资源状态的历史，用来检测状态变化
    const resourceStatusHistory = reactive({});
    
    // 使用共享的身份验证状态
    const { isAdmin } = useAuth()
    const { showToast } = useToast()
    
    // 组件卸载时清理
    onUnmounted(() => {
      if (ws.value) {
        ws.value.close();
      }
      
      if (refreshTimer.value) {
        clearInterval(refreshTimer.value);
      }
      
      if (wsReconnectTimer.value) {
        clearInterval(wsReconnectTimer.value);
      }
    });
    
    const filter = reactive({
      type: 'all',
      status: 'all'
    })
    
    const newResource = reactive({
      name: '',
      repo_id: '',
      description: '',
      resource_type: 'MODEL'
    })
    
    const isFormValid = computed(() => {
      return newResource.name && newResource.repo_id
    })
    
    const filteredResources = computed(() => {
      return resources_data.value.filter(resource => {
        const typeMatch = filter.type === 'all' || resource.resource_type === filter.type
        const statusMatch = filter.status === 'all' || resource.status === filter.status
        return typeMatch && statusMatch
      })
    })
    
    // 加载资源列表
    const loadResources = async () => {
      loading.value = true;
      error.value = null;
      
      try {
        // 加载资源列表
        const response = await api.apiClient.get('/api/resources');
        resources_data.value = response.data;
      } catch (err) {
        console.error('加载资源失败:', err);
        error.value = '无法加载资源列表，请检查网络连接后重试';
      } finally {
        loading.value = false;
      }
    };
    
    // 扫描本地资源
    const scanLocalResources = async () => {
      try {
        loading.value = true;
        
        const response = await api.apiClient.get('/api/resources/scan');
        
        const result = response.data;
        
        // 显示结果
        let message = '';
        
        if (result.added.length > 0) {
          message += `已添加: ${result.added.join(', ')}\n`;
        }
        
        if (result.existing.length > 0) {
          message += `已存在: ${result.existing.join(', ')}\n`;
        }
        
        if (result.errors.length > 0) {
          message += `错误: ${result.errors.join(', ')}`;
        }
        
        if (message) {
          showToast(message, 'info', 5000)
        } else {
          showToast('没有发现新的资源', 'info')
        }
        
        // 重新加载资源列表
        await loadResources();
      } catch (err) {
        console.error('扫描本地资源失败:', err);
        console.log("错误详情:", err.response?.data);
        console.log("错误状态码:", err.response?.status);
        
        showToast(`扫描失败: ${err.response?.data?.detail || '未知错误'}`, 'error')
      } finally {
        loading.value = false;
      }
    }
    
    // 添加新资源
    const addResource = async () => {
      try {
        const response = await api.apiClient.post('/api/resources', newResource)
        resources_data.value.push(response.data)
        resetForm()
        showAddDialog.value = false
        showToast('资源已添加', 'success')
      } catch (err) {
        console.error('添加资源失败:', err)
        showToast(`添加资源失败: ${err.response?.data?.detail || err.message}`, 'error')
      }
    }
    
    // 下载资源
    const downloadResource = async (resourceId) => {
      try {
        // 先检查该资源或其他资源是否正在下载
        const isAnyDownloading = resources_data.value.some(r => r.status === 'DOWNLOADING');
        const targetResource = resources_data.value.find(r => r.id === resourceId);
        
        if (!targetResource) {
          console.error(`找不到ID为${resourceId}的资源`);
          return;
        }
        
        if (targetResource.status === 'DOWNLOADING') {
          showToast('该资源正在下载中', 'info')
          return;
        }
        
        if (isAnyDownloading) {
          if (!confirm('已有资源正在下载中，是否开始新的下载？')) {
            return;
          }
        }
        
        // 先在本地更新状态，提高响应速度
        const resourceIndex = resources_data.value.findIndex(r => r.id === resourceId);
        if (resourceIndex !== -1) {
          const updatedResource = {
            ...resources_data.value[resourceIndex],
            status: 'PENDING',
            progress: 0
          };
          resources_data.value.splice(resourceIndex, 1, updatedResource);
        }
        
        // 发起下载请求
        await api.apiClient.post(`/api/resources/${resourceId}/download`, {
          source: 'OFFICIAL'
        });
        
        console.log(`已请求下载资源 ${resourceId}`);
      } catch (err) {
        console.error('请求下载失败:', err);
        showToast(`请求下载失败: ${err.response?.data?.detail || err.message}`, 'error')
        
        // 恢复原始状态
        await loadResources();
      }
    }
    
    // 取消下载
    const cancelDownload = async (resourceId) => {
      try {
        await api.apiClient.post(`/api/resources/${resourceId}/cancel`)
        await loadResources() // 刷新列表
      } catch (err) {
        console.error('取消下载失败:', err)
        showToast(`取消下载失败: ${err.response?.data?.detail || err.message}`, 'error')
      }
    }
    
    // 重试下载
    const retryDownload = async (resourceId) => {
      try {
        // 先在本地更新状态
        const resourceIndex = resources_data.value.findIndex(r => r.id === resourceId);
        if (resourceIndex !== -1) {
          const updatedResource = {
            ...resources_data.value[resourceIndex],
            status: 'PENDING',
            progress: 0
          };
          resources_data.value.splice(resourceIndex, 1, updatedResource);
        }
        
        // 调用重试API
        await api.apiClient.post(`/api/resources/${resourceId}/retry`, {
          source: 'OFFICIAL'
        });
        
        console.log(`已请求重试下载资源 ${resourceId}`);
      } catch (err) {
        console.error('重试下载失败:', err);
        showToast(`重试下载失败: ${err.response?.data?.detail || err.message}`, 'error')
        
        // 出错时重新加载资源
        await loadResources();
      }
    }
    
    // 删除资源
    const deleteResource = async (resourceId) => {
      if (confirm('确定要删除该资源吗？')) {
        try {
          await api.apiClient.delete(`/api/resources/${resourceId}`)
          resources_data.value = resources_data.value.filter(r => r.id !== resourceId)
          showToast('资源已删除', 'success')
        } catch (err) {
          console.error('删除资源失败:', err)
          showToast(`删除失败: ${err.response?.data?.detail || err.message}`, 'error')
        }
      }
    }
    
    // 查看详情
    const viewDetails = (resourceId) => {
      // 跳转到详情页面
      alert('查看详情功能尚未实现')
    }
    
    // 重置表单
    const resetForm = () => {
      newResource.name = ''
      newResource.repo_id = ''
      newResource.description = ''
      newResource.resource_type = 'MODEL'
    }
    
    // 格式化文件大小
    const formatSize = (sizeMB) => {
      if (sizeMB < 1024) {
        return `${sizeMB.toFixed(2)} MB`
      } else {
        return `${(sizeMB / 1024).toFixed(2)} GB`
      }
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
    
    const statusIcon = (status) => {
      const map = {
        'PENDING': 'hourglass_empty',
        'DOWNLOADING': 'download',
        'COMPLETED': 'check_circle',
        'FAILED': 'error',
        'CANCELLED': 'cancel'
      }
      return map[status] || 'help'
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
    
    // 检查管理员状态
    const checkAdminStatus = () => {
      alert(`当前管理员状态: ${isAdmin.value ? '是' : '否'}`)
    }
    
    // WebSocket连接与心跳
    const setupWebSocket = () => {
      // 清理现有连接
      if (ws.value) {
        ws.value.close();
      }
      
      // 建立新WebSocket连接
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${wsProtocol}//${window.location.host}/ws/resources`;
      
      ws.value = new WebSocket(wsUrl);
      
      ws.value.onopen = () => {
        console.log('WebSocket连接已建立');
        // 发送ping消息
        sendPing();
      };
      
      ws.value.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('WebSocket收到消息:', data);
          
          if (data.type === 'resource_update' && data.resource_id) {
            const resourceId = data.resource_id;
            const newStatus = data.status;
            const resourceName = data.resource?.name || '资源';
            
            // 获取旧状态
            const oldStatus = resourceStatusHistory[resourceId];
            
            // 更新状态历史
            resourceStatusHistory[resourceId] = newStatus;
            
            // 处理状态变化
            handleStatusChange(resourceId, newStatus, oldStatus, resourceName);
            
            // 查找要更新的资源
            const resourceIndex = resources_data.value.findIndex(r => r.id === data.resource_id);
            
            if (resourceIndex !== -1) {
              // 创建更新后的资源对象，确保保留现有属性
              const updatedResource = {
                ...resources_data.value[resourceIndex],
                ...data.resource  // 使用后端返回的完整资源数据
              };
              
              // 替换资源数组中的对象，确保Vue能够检测到变化
              resources_data.value.splice(resourceIndex, 1, updatedResource);
              
              console.log(`已更新资源 ${data.resource_id} 状态: ${oldStatus} -> ${updatedResource.status}`);
              
              // 如果资源状态从下载中变为已完成或失败，立即刷新页面获取完整信息
              if ((oldStatus === 'DOWNLOADING' && 
                  (updatedResource.status === 'COMPLETED' || updatedResource.status === 'FAILED')) ||
                  data.force_refresh) {
                console.log('资源下载状态已变更，立即刷新页面');
                loadResources();
              }
            } else {
              // 如果资源不在列表中，可能是新添加的资源，刷新列表
              console.log('收到未知资源更新，重新加载资源列表');
              loadResources();
            }
          } else if (data.type === 'pong') {
            // 收到pong响应，表明连接正常
            console.log('收到pong响应，WebSocket连接正常');
          }
        } catch (error) {
          console.error('解析WebSocket消息失败:', error);
        }
      };
      
      ws.value.onerror = (error) => {
        console.error('WebSocket错误:', error);
      };
      
      ws.value.onclose = () => {
        console.log('WebSocket连接已关闭，将尝试重新连接');
      };
    };
    
    // 发送ping消息
    const sendPing = () => {
      if (ws.value && ws.value.readyState === WebSocket.OPEN) {
        try {
          ws.value.send(JSON.stringify({ type: 'ping' }));
        } catch (error) {
          console.error('发送ping消息失败:', error);
        }
      }
    };
    
    // 检查并重新连接WebSocket
    const checkWebSocketConnection = () => {
      if (!ws.value || ws.value.readyState === WebSocket.CLOSED || ws.value.readyState === WebSocket.CLOSING) {
        console.log('WebSocket连接已断开，尝试重新连接');
        setupWebSocket();
      } else if (ws.value.readyState === WebSocket.OPEN) {
        // 连接正常，发送ping保持活跃
        sendPing();
      }
    };
    
    // 处理资源状态变化
    const handleStatusChange = (resourceId, newStatus, oldStatus, resourceName) => {
      // 只有在状态实际变化时才显示通知
      if (newStatus !== oldStatus) {
        if (newStatus === 'COMPLETED') {
          showToast(`${resourceName || '资源'} 下载完成！`, 'success')
          // 刷新资源列表
          loadResources()
        } else if (newStatus === 'FAILED') {
          showToast(`${resourceName || '资源'} 下载失败，请检查详情`, 'error')
          // 刷新资源列表
          loadResources()
        } else if (newStatus === 'DOWNLOADING' && (!oldStatus || oldStatus === 'PENDING')) {
          showToast(`${resourceName || '资源'} 开始下载`, 'info')
        }
      }
    }
    
    onMounted(async () => {
      await loadResources();
      
      // 初始化资源状态历史
      resources_data.value.forEach(resource => {
        resourceStatusHistory[resource.id] = resource.status;
      });
      
      // 设置WebSocket连接
      setupWebSocket();
      
      // 定期刷新资源列表（每60秒）
      refreshTimer.value = setInterval(async () => {
        if (!loading.value) {
          console.log('定期刷新资源列表');
          await loadResources();
        }
      }, 60000);
      
      // 定期检查WebSocket连接（每30秒）
      wsReconnectTimer.value = setInterval(() => {
        checkWebSocketConnection();
      }, 30000);
    })
    
    return {
      resources: resources_data,
      loading,
      error,
      filter,
      showAddDialog,
      newResource,
      filteredResources,
      isFormValid,
      isAdmin,
      loadResources,
      addResource,
      downloadResource,
      cancelDownload,
      retryDownload,
      deleteResource,
      viewDetails,
      formatSize,
      statusText,
      statusIcon,
      statusClass,
      scanLocalResources,
      checkAdminStatus
    }
  }
}
</script>

<style scoped>
.resource-page {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
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

.resource-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 24px;
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

.btn-warning {
  background-color: #ff9e80;
  color: white;
  border: 1px solid transparent;
}

.btn-warning:hover {
  background-color: #ff9e80;
  filter: brightness(1.1);
}

[data-theme="dark"] .btn-warning {
  background-color: #ff9e80;
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.2);
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

.btn-danger {
  background-color: #F44336;
  color: white;
}

[data-theme="dark"] .btn-danger {
  background-color: #F44336;
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.btn-sm {
  padding: 4px 8px;
  font-size: 12px;
}

.btn[disabled] {
  opacity: 0.6;
  cursor: not-allowed;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.resources-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 24px;
}

.resource-card {
  background-color: var(--bg-card);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 16px;
  transition: transform 0.2s, box-shadow 0.2s;
}

.resource-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.resource-header {
  display: flex;
  align-items: flex-start;
  margin-bottom: 12px;
}

.resource-type-badge {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  margin-right: 8px;
}

.resource-type-badge.model {
  background-color: #e3f2fd;
  color: #1976d2;
}

.resource-type-badge.dataset {
  background-color: #e8f5e9;
  color: #388e3c;
}

.resource-name {
  font-size: 18px;
  margin: 0;
  flex: 1;
}

.resource-info {
  margin-bottom: 16px;
}

.resource-repo {
  font-family: monospace;
  background-color: var(--bg-card-secondary);
  padding: 4px 8px;
  border-radius: 4px;
  margin-bottom: 8px;
  display: inline-block;
}

.resource-description {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.4;
}

.resource-status {
  margin-bottom: 12px;
}

.status-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
}

.status-pending { color: #ff9e80; }
.status-downloading { color: #2196f3; }
.status-completed { color: #4caf50; }
.status-failed { color: #f44336; }
.status-cancelled { color: #9e9e9e; }

.progress-bar {
  height: 8px;
  background-color: var(--bg-card-secondary);
  border-radius: 4px;
  margin-bottom: 8px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background-color: #2196f3;
  transition: width 0.3s;
}

.resource-size {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 16px;
}

.resource-actions {
  display: flex;
  gap: 8px;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 0;
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

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px 20px;
  text-align: center;
}

.empty-state .material-icons {
  font-size: 48px;
  color: var(--text-tertiary);
  margin-bottom: 16px;
}

.empty-state h3 {
  font-size: 20px;
  margin-bottom: 8px;
}

.empty-state p {
  color: var(--text-secondary);
  margin-bottom: 20px;
}

.error-message {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 20px;
  color: #f44336;
  text-align: center;
}

.error-message .material-icons {
  font-size: 48px;
  margin-bottom: 16px;
}

/* 对话框样式 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-dialog {
  background-color: var(--bg-card);
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  width: 100%;
  max-width: 480px;
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h2 {
  font-size: 20px;
  margin: 0;
}

.btn-close {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 18px;
  color: var(--text-tertiary);
}

.modal-body {
  padding: 24px 20px;
}

.modal-footer {
  padding: 16px 20px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  border-top: 1px solid var(--border-color);
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
}

.radio-group {
  display: flex;
  gap: 16px;
}

.radio-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

/* 响应式调整 */
@media (max-width: 768px) {
  .resources-grid {
    grid-template-columns: 1fr;
  }
  
  .resource-actions {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style> 