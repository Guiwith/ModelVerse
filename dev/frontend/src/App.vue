<template>
  <div class="app">
    <header class="app-bar">
      <div class="app-bar-title">
        <router-link to="/" class="logo-link">
          <img src="@/assets/logo/logo_b.png" alt="ModelVerse Logo" class="logo light-logo">
          <img src="@/assets/logo/logo_w.png" alt="ModelVerse Logo" class="logo dark-logo">
        </router-link>
      </div>
      <div class="app-bar-actions">
        <div class="nav-items">
          <router-link to="/" class="nav-link" v-if="isLoggedIn">
            <span class="material-icons">home</span>
            <span class="nav-text">首页</span>
          </router-link>
          
          <router-link to="/resources" class="nav-link" v-if="isLoggedIn">
            <span class="material-icons">storage</span>
            <span class="nav-text">资源管理</span>
          </router-link>
          
          <router-link to="/training" class="nav-link" v-if="isLoggedIn">
            <span class="material-icons">model_training</span>
            <span class="nav-text">模型训练</span>
          </router-link>
          
          <router-link to="/inference" class="nav-link" v-if="isLoggedIn">
            <span class="material-icons">smart_toy</span>
            <span class="nav-text">推理聊天</span>
          </router-link>
          
          <router-link to="/evaluation" class="nav-link" v-if="isLoggedIn">
            <span class="material-icons">analytics</span>
            <span class="nav-text">模型评估</span>
          </router-link>
          
          <router-link to="/shared" class="nav-link">
            <span class="material-icons">forum</span>
            <span class="nav-text">公开聊天</span>
          </router-link>
          
          <router-link to="/profile" class="nav-link" v-if="isLoggedIn">
            <span class="material-icons">person</span>
            <span class="nav-text">个人信息</span>
          </router-link>
          
          <router-link to="/admin" class="nav-link" v-if="isLoggedIn && isAdmin">
            <span class="material-icons">admin_panel_settings</span>
            <span class="nav-text">管理面板</span>
          </router-link>
          
          <a href="#" class="nav-link" v-if="isLoggedIn" @click.prevent="logout">
            <span class="material-icons">logout</span>
            <span class="nav-text">退出</span>
          </a>
          
          <router-link to="/login" class="nav-link" v-if="!isLoggedIn">
            <span class="material-icons">login</span>
            <span class="nav-text">登录</span>
          </router-link>
          
          <router-link to="/register" class="nav-link" v-if="!isLoggedIn">
            <span class="material-icons">person_add</span>
            <span class="nav-text">注册</span>
          </router-link>
        </div>
        <button class="btn-icon theme-toggle" @click="toggleTheme" title="切换主题">
          <span class="material-icons" v-if="currentTheme === 'light'">dark_mode</span>
          <span class="material-icons" v-else>light_mode</span>
        </button>
      </div>
    </header>
    
    <main class="container main-content">
      <router-view></router-view>
    </main>
    
    <footer class="footer">
      <div class="container">
        <div class="footer-content">
          <div class="footer-copyright">
            &copy; 2025 模型宇宙@ModelVerse
          </div>
          <div class="footer-links">
            <router-link to="/about" class="footer-link">关于我们</router-link>
            <router-link to="/privacy" class="footer-link">隐私政策</router-link>
          </div>
        </div>
      </div>
    </footer>
    <ToastContainer />
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
// @ts-ignore
import { useAuth } from './composables/auth'
// @ts-ignore
import { useTheme } from './composables/theme'
import ToastContainer from './components/ToastContainer.vue'

export default defineComponent({
  name: 'App',
  components: {
    ToastContainer
  },
  setup() {
    const router = useRouter()
    const { isAuthenticated: isLoggedIn, isAdmin, logout: authLogout, initAuth } = useAuth()
    const { currentTheme, toggleTheme } = useTheme()

    // 页面加载时检查身份验证状态
    onMounted(() => {
      initAuth()
    })

    // 登出方法
    const logout = () => {
      authLogout()
      router.push('/login')
    }

    return {
      isLoggedIn,
      isAdmin,
      logout,
      currentTheme,
      toggleTheme
    }
  }
})
</script>

<style>
/* 全局样式覆盖 */
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

/* App布局 */
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.main-content {
  flex: 1;
  padding: calc(var(--spacing-unit) * 2);
}

/* 顶部导航栏 */
.app-bar {
  background-color: var(--primary);
  color: var(--on-primary);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 16px;
  height: 64px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.dark-theme .app-bar {
  color: var(--text-primary);
}

.app-bar-title {
  font-size: 20px;
  font-weight: 500;
  display: flex;
  align-items: center;
}

.logo-link {
  text-decoration: none;
  display: block;
}

.logo {
  height: 32px;
  width: auto;
  display: block;
}

/* 默认显示亮色模式logo */
.dark-logo {
  display: none;
}

/* 暗色模式下切换logo */
.dark-theme .light-logo {
  display: none;
}

.dark-theme .dark-logo {
  display: block;
}

.app-bar-actions {
  display: flex;
  align-items: center;
}

/* 导航项目 */
.nav-items {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 16px;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--on-primary);
  text-decoration: none;
  opacity: 0.9;
  transition: opacity 0.2s ease, transform 0.2s ease;
  padding: 8px 0;
}

.dark-theme .nav-link {
  color: var(--text-primary);
}

.nav-link:hover {
  opacity: 1;
  transform: translateY(-2px);
}

.nav-text {
  font-size: 14px;
}

/* 按钮样式 */
.btn-icon {
  background: none;
  border: none;
  color: var(--on-primary);
  cursor: pointer;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s;
}

.dark-theme .btn-icon {
  color: var(--text-primary);
}

.btn-icon:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

/* 主题切换按钮 */
.theme-toggle {
  margin-left: 16px;
}

/* 页脚 */
.footer {
  background-color: var(--surface-color);
  color: var(--on-surface);
  padding: 24px 0;
  margin-top: 32px;
  border-top: 1px solid rgba(0, 0, 0, 0.12);
}

.dark-theme .footer {
  border-top-color: rgba(255, 255, 255, 0.12);
}

.footer-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}

.footer-copyright {
  color: var(--text-secondary);
}

.footer-links {
  display: flex;
  gap: 16px;
}

.footer-link {
  color: var(--primary);
  text-decoration: none;
  transition: opacity 0.2s;
}

.dark-theme .footer-link {
  color: var(--text-primary);
}

.footer-link:hover {
  opacity: 0.8;
}

/* 响应式调整 */
@media (max-width: 768px) {
  .nav-text {
    display: none;
  }
  
  .nav-items {
    gap: 8px;
  }
  
  .app-bar {
    padding: 0 8px;
  }
}
</style> 