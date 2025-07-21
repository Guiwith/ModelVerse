<template>
  <div class="profile-page">
    <header class="page-header">
      <h1>个人资料设置</h1>
      <p class="subtitle">更新您的个人信息和偏好设置</p>
    </header>
    
    <div class="grid">
      <div class="grid-item">
        <div class="card">
          <div class="card-header">
            <h2>基本信息</h2>
          </div>
          
          <div v-if="loading" class="loader">
            <div class="loader-circle"></div>
          </div>
          <div v-else-if="error" class="alert alert-error">
            <span class="material-icons">error</span>
            <p>{{ error }}</p>
          </div>
          <div v-else>
            <form @submit.prevent="saveProfile" class="profile-form">
              <div class="avatar-section">
                <div class="avatar-container">
                  <img v-if="avatarPreview" :src="avatarPreview" alt="头像预览" class="avatar-preview" />
                  <span v-else-if="profile.avatar_url" class="avatar-preview">
                    <img :src="profile.avatar_url" alt="用户头像" />
                  </span>
                  <span v-else class="material-icons avatar-placeholder">account_circle</span>
                  
                  <div class="avatar-upload-overlay">
                    <label for="avatar-upload" class="avatar-upload-label">
                      <span class="material-icons">photo_camera</span>
                    </label>
                    <input 
                      type="file" 
                      id="avatar-upload" 
                      accept="image/*" 
                      @change="handleAvatarChange" 
                      class="avatar-upload-input" 
                    />
                  </div>
                </div>
                <div class="avatar-info">
                  <p>允许的格式: JPG, PNG, GIF</p>
                  <p>最大文件大小: 2MB</p>
                  <button 
                    type="button" 
                    class="btn btn-secondary btn-sm" 
                    v-if="avatarChanged" 
                    @click="uploadAvatar"
                    :disabled="avatarUploading"
                  >
                    <span class="material-icons" v-if="avatarUploading">sync</span>
                    <span v-else>上传头像</span>
                  </button>
                </div>
              </div>
              
              <div class="form-group">
                <label for="username" class="form-label">用户名</label>
                <input 
                  type="text" 
                  id="username" 
                  v-model="profile.username" 
                  disabled 
                  class="form-control" 
                />
                <small>用户名不可修改</small>
              </div>
              
              <div class="form-group">
                <label for="display_name" class="form-label">显示名称</label>
                <input 
                  type="text" 
                  id="display_name" 
                  v-model="profile.display_name" 
                  class="form-control" 
                  placeholder="输入您希望显示的名称" 
                />
              </div>
              
              <div class="form-group">
                <label for="email" class="form-label">电子邮箱</label>
                <input 
                  type="email" 
                  id="email" 
                  v-model="profile.email" 
                  class="form-control" 
                  placeholder="输入电子邮箱" 
                />
              </div>
              
              <div class="form-group">
                <label for="phone" class="form-label">手机号码</label>
                <input 
                  type="tel" 
                  id="phone" 
                  v-model="profile.phone" 
                  class="form-control" 
                  placeholder="输入手机号码" 
                />
              </div>
              
              <div v-if="saveSuccess" class="alert alert-success">
                <span class="material-icons">check_circle</span>
                <p>个人资料已成功更新！</p>
              </div>
              
              <div class="form-actions">
                <button type="button" class="btn btn-secondary" @click="resetForm">重置</button>
                <button type="submit" class="btn btn-primary" :disabled="saving">
                  <span class="material-icons" v-if="saving">sync</span>
                  <span v-else>保存更改</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
      
      <div class="grid-item">
        <div class="card">
          <div class="card-header">
            <h2>安全设置</h2>
          </div>
          
          <form @submit.prevent="changePassword" class="password-form">
            <div class="form-group">
              <label for="current_password" class="form-label">当前密码</label>
              <input 
                type="password" 
                id="current_password" 
                v-model="passwordData.currentPassword" 
                class="form-control" 
                placeholder="输入当前密码" 
              />
            </div>
            
            <div class="form-group">
              <label for="new_password" class="form-label">新密码</label>
              <input 
                type="password" 
                id="new_password" 
                v-model="passwordData.newPassword" 
                class="form-control" 
                placeholder="输入新密码" 
              />
            </div>
            
            <div class="form-group">
              <label for="confirm_password" class="form-label">确认新密码</label>
              <input 
                type="password" 
                id="confirm_password" 
                v-model="passwordData.confirmPassword" 
                class="form-control" 
                placeholder="再次输入新密码" 
              />
            </div>
            
            <div v-if="passwordError" class="alert alert-error">
              <span class="material-icons">error</span>
              <p>{{ passwordError }}</p>
            </div>
            
            <div v-if="passwordSuccess" class="alert alert-success">
              <span class="material-icons">check_circle</span>
              <p>密码已成功更新！</p>
            </div>
            
            <div class="form-actions">
              <button type="submit" class="btn btn-primary" :disabled="changingPassword">
                <span class="material-icons" v-if="changingPassword">sync</span>
                <span v-else>更新密码</span>
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, reactive, onMounted } from 'vue'
import { useAuth } from '../composables/auth'
import { useApi } from '../composables/api'

export default defineComponent({
  name: 'Profile',
  setup() {
    const { currentUser } = useAuth()
    const { getUserProfile, updateUserProfile, updateAvatar, changeUserPassword } = useApi()
    
    // 基本信息表单
    const profile = reactive({
      username: '',
      display_name: '',
      email: '',
      phone: '',
      avatar_url: ''
    })
    
    // 头像上传状态
    const avatarFile = ref<File | null>(null)
    const avatarPreview = ref('')
    const avatarChanged = ref(false)
    const avatarUploading = ref(false)
    
    // 加载和保存状态
    const loading = ref(true)
    const error = ref('')
    const saving = ref(false)
    const saveSuccess = ref(false)
    
    // 密码修改表单
    const passwordData = reactive({
      currentPassword: '',
      newPassword: '',
      confirmPassword: ''
    })
    
    // 密码修改状态
    const changingPassword = ref(false)
    const passwordError = ref('')
    const passwordSuccess = ref(false)
    
    // 加载用户数据
    const loadProfile = async () => {
      try {
        loading.value = true
        const data = await getUserProfile() as {
          username: string;
          display_name?: string;
          email: string;
          phone?: string;
          avatar_url?: string;
        }
        
        // 填充表单数据
        profile.username = data.username
        profile.display_name = data.display_name || ''
        profile.email = data.email
        profile.phone = data.phone || ''
        profile.avatar_url = data.avatar_url || ''
        
      } catch (err: any) {
        error.value = '获取个人资料失败: ' + (err.message || '未知错误')
      } finally {
        loading.value = false
      }
    }
    
    // 处理头像选择
    const handleAvatarChange = (event: Event) => {
      const input = event.target as HTMLInputElement
      if (!input.files || input.files.length === 0) {
        return
      }
      
      const file = input.files[0]
      
      // 检查文件大小 (最大2MB)
      if (file.size > 2 * 1024 * 1024) {
        error.value = '文件大小不能超过2MB'
        return
      }
      
      // 检查文件类型
      if (!['image/jpeg', 'image/png', 'image/gif'].includes(file.type)) {
        error.value = '只支持JPG, PNG, GIF格式的图片'
        return
      }
      
      avatarFile.value = file
      avatarChanged.value = true
      
      // 创建预览
      const reader = new FileReader()
      reader.onload = (e) => {
        if (e.target) {
          avatarPreview.value = e.target.result as string
        }
      }
      reader.readAsDataURL(file)
    }
    
    // 上传头像
    const uploadAvatar = async () => {
      if (!avatarFile.value) return
      
      try {
        avatarUploading.value = true
        const formData = new FormData()
        formData.append('avatar', avatarFile.value)
        
        const result = await updateAvatar(formData) as { avatar_url: string }
        
        // 更新头像URL
        profile.avatar_url = result.avatar_url
        
        // 重置状态
        avatarChanged.value = false
        avatarPreview.value = ''
        avatarFile.value = null
        
        saveSuccess.value = true
        setTimeout(() => { saveSuccess.value = false }, 3000)
      } catch (err: any) {
        error.value = '上传头像失败: ' + (err.message || '未知错误')
      } finally {
        avatarUploading.value = false
      }
    }
    
    // 保存个人资料
    const saveProfile = async () => {
      try {
        saving.value = true
        
        await updateUserProfile({
          display_name: profile.display_name,
          email: profile.email,
          phone: profile.phone
        })
        
        saveSuccess.value = true
        setTimeout(() => { saveSuccess.value = false }, 3000)
      } catch (err: any) {
        error.value = '保存个人资料失败: ' + (err.message || '未知错误')
      } finally {
        saving.value = false
      }
    }
    
    // 重置表单
    const resetForm = () => {
      loadProfile()
      avatarPreview.value = ''
      avatarFile.value = null
      avatarChanged.value = false
      error.value = ''
    }
    
    // 修改密码
    const changePassword = async () => {
      // 重置状态
      passwordError.value = ''
      passwordSuccess.value = false
      
      // 验证表单
      if (!passwordData.currentPassword) {
        passwordError.value = '请输入当前密码'
        return
      }
      
      if (!passwordData.newPassword) {
        passwordError.value = '请输入新密码'
        return
      }
      
      if (passwordData.newPassword.length < 6) {
        passwordError.value = '新密码长度至少为6个字符'
        return
      }
      
      if (passwordData.newPassword !== passwordData.confirmPassword) {
        passwordError.value = '两次输入的新密码不一致'
        return
      }
      
      try {
        changingPassword.value = true
        
        await changeUserPassword({
          current_password: passwordData.currentPassword,
          new_password: passwordData.newPassword
        })
        
        // 重置表单
        passwordData.currentPassword = ''
        passwordData.newPassword = ''
        passwordData.confirmPassword = ''
        
        passwordSuccess.value = true
        setTimeout(() => { passwordSuccess.value = false }, 3000)
      } catch (err: any) {
        passwordError.value = '修改密码失败: ' + (err.response?.data?.detail || err.message || '未知错误')
      } finally {
        changingPassword.value = false
      }
    }
    
    onMounted(() => {
      loadProfile()
    })
    
    return {
      profile,
      loading,
      error,
      saving,
      saveSuccess,
      avatarPreview,
      avatarChanged,
      avatarUploading,
      passwordData,
      changingPassword,
      passwordError,
      passwordSuccess,
      handleAvatarChange,
      uploadAvatar,
      saveProfile,
      resetForm,
      changePassword
    }
  }
})
</script>

<style scoped>
.profile-page {
  padding: calc(var(--spacing-unit) * 2) 0;
}

.page-header {
  margin-bottom: calc(var(--spacing-unit) * 4);
}

.subtitle {
  color: var(--text-secondary);
  opacity: 0.8;
  margin-top: calc(var(--spacing-unit) * -1);
}

[data-theme="dark"] .subtitle {
  color: var(--text-secondary);
  opacity: 0.9;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: calc(var(--spacing-unit) * 3);
}

.form-group {
  margin-bottom: calc(var(--spacing-unit) * 3);
}

.form-label {
  display: block;
  margin-bottom: calc(var(--spacing-unit) * 1);
  font-weight: var(--font-weight-medium);
}

.form-control {
  width: 100%;
}

small {
  display: block;
  color: var(--secondary-color);
  margin-top: calc(var(--spacing-unit) * 0.5);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: calc(var(--spacing-unit) * 2);
  margin-top: calc(var(--spacing-unit) * 4);
}

.btn-sm {
  padding: calc(var(--spacing-unit) * 0.75) calc(var(--spacing-unit) * 1.5);
  font-size: 0.9rem;
}

.avatar-section {
  display: flex;
  gap: calc(var(--spacing-unit) * 3);
  margin-bottom: calc(var(--spacing-unit) * 4);
}

.avatar-container {
  position: relative;
  width: 100px;
  height: 100px;
  border-radius: 50%;
  overflow: hidden;
  background-color: var(--surface-color);
  box-shadow: var(--elevation-1);
}

.avatar-preview,
.avatar-placeholder {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-placeholder {
  font-size: 64px;
  color: var(--primary-color);
}

.avatar-upload-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 40%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.avatar-container:hover .avatar-upload-overlay {
  opacity: 1;
}

.avatar-upload-label {
  color: white;
  cursor: pointer;
}

.avatar-upload-input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.avatar-info {
  display: flex;
  flex-direction: column;
}

.avatar-info p {
  margin: 0 0 calc(var(--spacing-unit) * 0.5) 0;
  font-size: var(--font-size-small);
  color: var(--secondary-color);
}

.alert {
  padding: calc(var(--spacing-unit) * 1.5);
  border-radius: var(--border-radius);
  margin-bottom: calc(var(--spacing-unit) * 2);
  display: flex;
  align-items: center;
  gap: calc(var(--spacing-unit) * 1);
}

.alert p {
  margin: 0;
}

.alert-error {
  background-color: rgba(211, 47, 47, 0.1);
  color: #d32f2f;
}

.alert-success {
  background-color: rgba(46, 125, 50, 0.1);
  color: #2e7d32;
}

/* 响应式调整 */
@media (max-width: 960px) {
  .grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 600px) {
  .avatar-section {
    flex-direction: column;
    align-items: center;
  }
  
  .avatar-info {
    text-align: center;
  }
  
  .form-actions {
    flex-direction: column;
  }
  
  .form-actions button {
    width: 100%;
  }
}
</style> 