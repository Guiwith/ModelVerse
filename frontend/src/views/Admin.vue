<template>
  <div class="admin-page">
    <h1>管理员面板</h1>
    
    <div class="admin-dashboard card">
      <h2>仪表盘</h2>
      <div v-if="loading">加载中...</div>
      <div v-else-if="error">{{ error }}</div>
      <div v-else class="dashboard-stats">
        <div class="stat-card">
          <div class="stat-value">{{ dashboardData.user_count }}</div>
          <div class="stat-label">用户数量</div>
        </div>
      </div>
    </div>
    
    <div class="card">
      <h2>用户管理</h2>
      <div v-if="usersLoading">加载中...</div>
      <div v-else-if="usersError">{{ usersError }}</div>
      <div v-else>
        <table class="users-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>用户名</th>
              <th>邮箱</th>
              <th>创建时间</th>
              <th>权限</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id">
              <td>{{ user.id }}</td>
              <td>{{ user.username }}</td>
              <td>{{ user.email }}</td>
              <td>{{ formatDate(user.created_at) }}</td>
              <td>{{ user.is_admin ? '管理员' : '用户' }}</td>
              <td class="action-buttons">
                <button 
                  class="btn btn-small btn-danger" 
                  @click="handleDeleteUser(user)"
                  :disabled="user.id === currentUser?.id"
                  title="删除用户"
                >
                  删除
                </button>
                <button 
                  class="btn btn-small" 
                  @click="handleShowChangePassword(user)"
                  title="修改密码"
                >
                  修改密码
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    
    <div class="card">
      <h2>添加新用户</h2>
      <form @submit.prevent="handleAddUser">
        <div class="form-group">
          <label for="new-username">用户名</label>
          <input 
            type="text" 
            id="new-username" 
            v-model="newUser.username" 
            required 
            placeholder="请输入用户名"
          />
        </div>
        
        <div class="form-group">
          <label for="new-email">邮箱</label>
          <input 
            type="email" 
            id="new-email" 
            v-model="newUser.email" 
            required 
            placeholder="请输入邮箱"
          />
        </div>
        
        <div class="form-group">
          <label for="new-password">密码</label>
          <input 
            type="password" 
            id="new-password" 
            v-model="newUser.password" 
            required 
            placeholder="请输入密码"
          />
        </div>
        
        <div class="form-group checkbox">
          <input 
            type="checkbox" 
            id="new-is-admin" 
            v-model="newUser.is_admin"
          />
          <label for="new-is-admin">管理员权限</label>
        </div>
        
        <div v-if="addUserError" class="error">{{ addUserError }}</div>
        
        <button type="submit" class="btn" :disabled="addingUser">
          {{ addingUser ? '添加中...' : '添加用户' }}
        </button>
      </form>
    </div>
    
    <!-- 修改密码弹窗 -->
    <div class="modal" v-if="showChangePasswordModal">
      <div class="modal-content">
        <div class="modal-header">
          <h3>修改 {{ selectedUser?.username }} 的密码</h3>
          <button class="close-btn" @click="showChangePasswordModal = false">&times;</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label for="new-user-password">新密码</label>
            <input 
              type="password" 
              id="new-user-password" 
              v-model="newPassword" 
              required 
              placeholder="请输入新密码"
            />
          </div>
          <div class="form-group">
            <label for="confirm-user-password">确认新密码</label>
            <input 
              type="password" 
              id="confirm-user-password" 
              v-model="confirmPassword" 
              required 
              placeholder="请再次输入新密码"
            />
          </div>
          
          <div v-if="passwordError" class="error">{{ passwordError }}</div>
          <div v-if="passwordSuccess" class="success">密码修改成功</div>
          
          <div class="modal-actions">
            <button 
              class="btn" 
              @click="handleChangePassword" 
              :disabled="changingPassword || !newPassword || !confirmPassword"
            >
              {{ changingPassword ? '修改中...' : '修改密码' }}
            </button>
            <button class="btn btn-secondary" @click="showChangePasswordModal = false">取消</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, reactive, onMounted } from 'vue'
import { useApi } from '../composables/api'
import { useAuth } from '../composables/auth'
import type { User, UserCreate, DashboardData } from '../types/models'

export default defineComponent({
  name: 'Admin',
  setup() {
    const { getAdminDashboard, getUsers, createUser, deleteUser, adminChangeUserPassword } = useApi()
    const { currentUser } = useAuth()
    
    // 仪表盘数据
    const dashboardData = ref<DashboardData>({ user_count: 0 })
    const loading = ref(true)
    const error = ref('')
    
    // 用户列表数据
    const users = ref<User[]>([])
    const usersLoading = ref(true)
    const usersError = ref('')
    
    // 新用户表单
    const newUser = reactive<UserCreate>({
      username: '',
      email: '',
      password: '',
      is_admin: false
    })
    const addingUser = ref(false)
    const addUserError = ref('')
    
    // 修改密码弹窗
    const showChangePasswordModal = ref(false)
    const selectedUser = ref<User | null>(null)
    const newPassword = ref('')
    const confirmPassword = ref('')
    const passwordError = ref('')
    const passwordSuccess = ref(false)
    const changingPassword = ref(false)
    
    // 加载仪表盘数据
    const loadDashboard = async () => {
      try {
        loading.value = true
        dashboardData.value = await getAdminDashboard() as DashboardData
      } catch (err: any) {
        error.value = '加载仪表盘数据失败: ' + (err.message || '未知错误')
      } finally {
        loading.value = false
      }
    }
    
    // 加载用户列表
    const loadUsers = async () => {
      try {
        usersLoading.value = true
        users.value = await getUsers() as User[]
      } catch (err: any) {
        usersError.value = '加载用户列表失败: ' + (err.message || '未知错误')
      } finally {
        usersLoading.value = false
      }
    }
    
    // 添加新用户
    const handleAddUser = async () => {
      try {
        addingUser.value = true
        addUserError.value = ''
        
        await createUser(newUser)
        
        // 重置表单
        newUser.username = ''
        newUser.email = ''
        newUser.password = ''
        newUser.is_admin = false
        
        // 重新加载用户列表和仪表盘
        await Promise.all([loadUsers(), loadDashboard()])
      } catch (err: any) {
        addUserError.value = '添加用户失败: ' + (err.response?.data?.detail || err.message || '未知错误')
      } finally {
        addingUser.value = false
      }
    }
    
    // 删除用户
    const handleDeleteUser = async (user: User) => {
      if (!confirm(`确定要删除用户 ${user.username} 吗？此操作不可恢复！`)) {
        return
      }
      
      try {
        await deleteUser(user.id)
        
        // 重新加载用户列表和仪表盘
        await Promise.all([loadUsers(), loadDashboard()])
      } catch (err: any) {
        alert('删除用户失败: ' + (err.response?.data?.detail || err.message || '未知错误'))
      }
    }
    
    // 显示修改密码弹窗
    const handleShowChangePassword = (user: User) => {
      selectedUser.value = user
      newPassword.value = ''
      confirmPassword.value = ''
      passwordError.value = ''
      passwordSuccess.value = false
      showChangePasswordModal.value = true
    }
    
    // 修改用户密码
    const handleChangePassword = async () => {
      if (!selectedUser.value) return
      
      // 验证表单
      if (!newPassword.value) {
        passwordError.value = '请输入新密码'
        return
      }
      
      if (newPassword.value.length < 6) {
        passwordError.value = '新密码长度至少为6个字符'
        return
      }
      
      if (newPassword.value !== confirmPassword.value) {
        passwordError.value = '两次输入的新密码不一致'
        return
      }
      
      try {
        changingPassword.value = true
        passwordError.value = ''
        
        await adminChangeUserPassword(selectedUser.value.id, newPassword.value)
        
        passwordSuccess.value = true
        
        // 3秒后关闭弹窗
        setTimeout(() => {
          showChangePasswordModal.value = false
        }, 2000)
      } catch (err: any) {
        passwordError.value = '修改密码失败: ' + (err.response?.data?.detail || err.message || '未知错误')
      } finally {
        changingPassword.value = false
      }
    }
    
    // 格式化日期
    const formatDate = (dateString: string) => {
      try {
        const date = new Date(dateString)
        return date.toLocaleString()
      } catch (e) {
        return dateString
      }
    }
    
    onMounted(() => {
      loadDashboard()
      loadUsers()
    })
    
    return {
      dashboardData,
      loading,
      error,
      users,
      usersLoading,
      usersError,
      newUser,
      addingUser,
      addUserError,
      currentUser,
      handleAddUser,
      handleDeleteUser,
      handleShowChangePassword,
      showChangePasswordModal,
      selectedUser,
      newPassword,
      confirmPassword,
      passwordError,
      passwordSuccess,
      changingPassword,
      handleChangePassword,
      formatDate
    }
  }
})
</script>

<style scoped>
.admin-page {
  padding: 1rem 0;
}

.dashboard-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-top: 1rem;
}

.stat-card {
  flex: 1;
  min-width: 150px;
  padding: 1.5rem;
  background-color: var(--primary-color);
  color: var(--on-primary);
  border-radius: var(--border-radius);
  text-align: center;
  box-shadow: var(--elevation-1);
  transition: transform 0.2s ease, box-shadow 0.3s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--elevation-2);
}

.stat-value {
  font-size: 2.5rem;
  font-weight: bold;
  margin-bottom: 0.5rem;
}

.stat-label {
  font-size: 1rem;
  opacity: 0.8;
}

.users-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  margin-top: 1rem;
  border-radius: var(--border-radius);
  overflow: hidden;
}

.users-table th,
.users-table td {
  padding: 0.75rem;
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
  transition: background-color 0.3s ease;
}

.dark-theme .users-table th,
.dark-theme .users-table td {
  border-bottom-color: rgba(255, 255, 255, 0.12);
}

.users-table th {
  font-weight: 500;
  text-align: left;
  background-color: rgba(0, 0, 0, 0.02);
}

.dark-theme .users-table th {
  background-color: rgba(255, 255, 255, 0.05);
}

.users-table tr:hover {
  background-color: rgba(0, 0, 0, 0.04);
}

.dark-theme .users-table tr:hover {
  background-color: rgba(255, 255, 255, 0.04);
}

.action-buttons {
  display: flex;
  gap: 0.5rem;
}

@media (max-width: 768px) {
  .action-buttons {
    flex-direction: column;
    gap: 0.3rem;
  }
}

.dark-theme .action-buttons {
  gap: 0.75rem;
}

.btn-small {
  padding: 0.35rem 0.75rem;
  font-size: 0.85rem;
}

.dark-theme .btn-small {
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

.btn-danger {
  background-color: var(--error-color);
  color: white;
}

.btn-secondary {
  background-color: var(--secondary-color);
  color: var(--on-secondary);
}

.dark-theme .btn-danger {
  background-color: var(--error-color);
  box-shadow: 0 0 8px rgba(var(--error-color-rgb, 255, 99, 71), 0.5);
}

.dark-theme .btn-secondary {
  background-color: var(--secondary-color);
  box-shadow: 0 0 8px rgba(var(--secondary-color-rgb, 100, 100, 100), 0.3);
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
}

.form-group input[type="text"],
.form-group input[type="email"],
.form-group input[type="password"] {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 20px;
  background-color: var(--surface-color);
  color: var(--on-surface);
  transition: border-color 0.3s ease, box-shadow 0.3s ease, transform 0.2s ease;
}

.dark-theme .form-group input[type="text"],
.dark-theme .form-group input[type="email"],
.dark-theme .form-group input[type="password"] {
  border-color: rgba(255, 255, 255, 0.12);
}

.form-group input:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(201, 123, 99, 0.2);
  transform: translateY(-1px);
}

.checkbox {
  display: flex;
  align-items: center;
}

.checkbox input {
  margin-right: 0.5rem;
}

.checkbox label {
  margin-bottom: 0;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.75rem 1.5rem;
  background-color: var(--primary-color);
  color: var(--on-primary);
  border: none;
  border-radius: 20px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease;
  position: relative;
  overflow: hidden;
}

.btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.btn:active {
  transform: translateY(0);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.error {
  color: var(--error-color);
  margin-bottom: 1rem;
}

.success {
  color: var(--success-color);
  margin-bottom: 1rem;
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

.dark-theme .modal {
  background-color: rgba(0, 0, 0, 0.7);
}

.modal-content {
  background-color: var(--background-color);
  border-radius: var(--border-radius);
  box-shadow: var(--elevation-3);
  width: 100%;
  max-width: 500px;
  max-height: 90vh;
  overflow-y: auto;
  animation: modal-appear 0.3s ease;
}

.dark-theme .modal-content {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

@keyframes modal-appear {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
}

.dark-theme .modal-header {
  border-bottom-color: rgba(255, 255, 255, 0.12);
}

.modal-header h3 {
  margin: 0;
  font-size: 1.25rem;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  color: var(--on-surface);
  cursor: pointer;
  padding: 0;
  margin: 0;
  line-height: 1;
}

.modal-body {
  padding: 1.5rem;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 1.5rem;
}
</style> 