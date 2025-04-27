<template>
  <div class="login-page">
    <div class="card login-card">
      <div class="login-header">
        <div class="logo-animation">
          <span class="logo-letter">M</span>
          <span class="logo-letter">o</span>
          <span class="logo-letter">d</span>
          <span class="logo-letter">e</span>
          <span class="logo-letter">l</span>
          <span class="logo-letter">V</span>
          <span class="logo-letter">e</span>
          <span class="logo-letter">r</span>
          <span class="logo-letter">s</span>
          <span class="logo-letter">e</span>
        </div>
        <p class="login-subtitle">创建新账号</p>
      </div>
      
      <form @submit.prevent="handleRegister">
        <div class="form-group">
          <label for="username" class="form-label">用户名</label>
          <input 
            type="text" 
            id="username" 
            v-model="username" 
            required 
            placeholder="请输入用户名"
            class="form-control"
          />
        </div>
        
        <div class="form-group">
          <label for="password" class="form-label">密码</label>
          <input 
            type="password" 
            id="password" 
            v-model="password" 
            required 
            placeholder="请输入密码"
            class="form-control"
          />
        </div>
        
        <div class="form-group">
          <label for="confirmPassword" class="form-label">确认密码</label>
          <input 
            type="password" 
            id="confirmPassword" 
            v-model="confirmPassword" 
            required 
            placeholder="请再次输入密码"
            class="form-control"
          />
        </div>
        
        <div class="form-group captcha-group">
          <label for="captcha" class="form-label">验证码</label>
          <div class="captcha-container">
            <input 
              type="text" 
              id="captcha" 
              v-model="captcha" 
              required 
              placeholder="请输入验证码"
              class="form-control captcha-input"
            />
            <div class="captcha-image" @click="refreshCaptcha">
              <img v-if="captchaUrl" :src="captchaUrl" alt="验证码" />
              <div v-else class="captcha-loading">加载中...</div>
            </div>
          </div>
        </div>
        
        <div v-if="error" class="text-error mb-2">{{ error }}</div>
        
        <button type="submit" class="btn btn-primary login-btn" :disabled="loading">
          <span class="material-icons" v-if="loading">sync</span>
          <span v-else>注册</span>
        </button>
        
        <div class="login-link">
          <p>已有账号？<router-link to="/login">去登录</router-link></p>
        </div>
      </form>
    </div>
    <div class="animated-bg">
      <div class="bg-circle"></div>
      <div class="bg-circle"></div>
      <div class="bg-circle"></div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '../composables/api'

export default defineComponent({
  name: 'Register',
  setup() {
    const router = useRouter()
    const { registerUser, getCaptcha } = useApi()
    
    const username = ref('')
    const password = ref('')
    const confirmPassword = ref('')
    const captcha = ref('')
    const captchaId = ref('')
    const captchaUrl = ref('')
    const loading = ref(false)
    const error = ref('')
    
    // 获取验证码
    const refreshCaptcha = async () => {
      try {
        const result = await getCaptcha()
        captchaId.value = result.captchaId
        captchaUrl.value = result.captchaUrl
      } catch (err) {
        error.value = '获取验证码失败，请刷新页面重试'
      }
    }
    
    // 处理注册
    const handleRegister = async () => {
      // 重置错误信息
      error.value = ''
      
      // 验证表单
      if (!username.value || !password.value || !confirmPassword.value || !captcha.value) {
        error.value = '请填写所有字段'
        return
      }
      
      if (password.value !== confirmPassword.value) {
        error.value = '两次输入的密码不一致'
        return
      }
      
      if (password.value.length < 6) {
        error.value = '密码长度至少为6个字符'
        return
      }
      
      loading.value = true
      
      try {
        await registerUser({
          username: username.value,
          password: password.value,
          captcha: captcha.value,
          captcha_id: captchaId.value
        })
        
        // 注册成功，跳转到登录页
        router.push({
          path: '/login',
          query: { registered: 'success' }
        })
      } catch (err: any) {
        error.value = err.response?.data?.detail || '注册失败，请稍后重试'
        // 刷新验证码
        refreshCaptcha()
      } finally {
        loading.value = false
      }
    }
    
    // Logo动画效果初始化
    onMounted(() => {
      // 初始化验证码
      refreshCaptcha()
      
      // 字母动画
      const letters = document.querySelectorAll('.logo-letter');
      letters.forEach((letter, index) => {
        setTimeout(() => {
          letter.classList.add('animate');
        }, index * 120); // 每个字母依次延迟
      });
    })
    
    return {
      username,
      password,
      confirmPassword,
      captcha,
      captchaUrl,
      loading,
      error,
      handleRegister,
      refreshCaptcha
    }
  }
})
</script>

<style scoped>
.login-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 90vh;
  padding: calc(var(--spacing-unit) * 2);
  position: relative;
  overflow: hidden;
}

.login-card {
  width: 100%;
  max-width: 450px;
  padding: calc(var(--spacing-unit) * 3);
  position: relative;
  z-index: 2;
  backdrop-filter: blur(5px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  background-color: rgba(255, 255, 255, 0.8);
}

.dark-theme .login-card {
  background-color: rgba(48, 48, 48, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.login-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: calc(var(--spacing-unit) * 4);
}

.logo-animation {
  display: flex;
  justify-content: center;
  margin-bottom: var(--spacing-unit);
  height: 60px;
  align-items: center;
}

.logo-letter {
  display: inline-block;
  font-size: 2.5rem;
  font-weight: 700;
  color: var(--primary-color);
  transform: translateY(0);
  opacity: 0;
  transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275), opacity 0.3s ease;
}

.logo-letter.animate {
  transform: translateY(-10px);
  opacity: 1;
  animation: letterPop 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
}

@keyframes letterPop {
  0% { transform: translateY(20px); opacity: 0; }
  60% { transform: translateY(-5px); opacity: 1; }
  80% { transform: translateY(2px); }
  100% { transform: translateY(0); opacity: 1; }
}

.login-subtitle {
  color: var(--secondary-color);
  font-size: 1.1rem;
  margin-top: var(--spacing-unit);
  opacity: 0;
  animation: fadeIn 1s ease 1s forwards;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* 验证码样式 */
.captcha-group {
  position: relative;
}

.captcha-container {
  display: flex;
  gap: var(--spacing-unit);
  align-items: stretch;
}

.captcha-input {
  flex: 1;
}

.captcha-image {
  width: 120px;
  height: 48px;
  background-color: rgba(0, 0, 0, 0.05);
  border-radius: var(--border-radius);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: transform 0.2s ease;
}

.captcha-image:hover {
  transform: scale(1.02);
}

.captcha-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.captcha-loading {
  font-size: 0.9rem;
  color: var(--secondary-color);
}

.login-btn {
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--spacing-unit);
  height: 50px;
  font-size: 1.1rem;
  margin-top: calc(var(--spacing-unit) * 3);
  position: relative;
  overflow: hidden;
}

.login-btn::after {
  content: '';
  position: absolute;
  background: rgba(255, 255, 255, 0.3);
  width: 100%;
  height: 100%;
  left: 0;
  top: 0;
  opacity: 0;
  transform: scale(0);
  transition: transform 0.3s ease, opacity 0.3s ease;
}

.login-btn:hover::after {
  opacity: 1;
  transform: scale(1);
}

.login-btn .material-icons {
  animation: spin 1.5s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.login-link {
  text-align: center;
  margin-top: calc(var(--spacing-unit) * 3);
}

.login-link a {
  color: var(--primary-color);
  font-weight: 500;
  text-decoration: none;
  transition: color 0.3s ease;
}

.login-link a:hover {
  text-decoration: underline;
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
  background: linear-gradient(45deg, var(--primary-color), var(--primary-variant));
  opacity: 0.2;
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

/* 表单控件 */
.form-group {
  margin-bottom: calc(var(--spacing-unit) * 2.5);
  position: relative;
}

.form-control {
  transition: all 0.3s ease;
  background-color: transparent;
  border: 1px solid rgba(0, 0, 0, 0.2);
}

.dark-theme .form-control {
  border-color: rgba(255, 255, 255, 0.2);
  background-color: rgba(0, 0, 0, 0.1);
}

.form-control:focus {
  background-color: rgba(255, 255, 255, 0.9);
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(201, 123, 99, 0.25);
}

.dark-theme .form-control:focus {
  background-color: rgba(0, 0, 0, 0.2);
}

/* 移动端适配 */
@media (max-width: 600px) {
  .login-page {
    align-items: flex-start;
    padding-top: 10vh;
  }
  
  .login-card {
    padding: calc(var(--spacing-unit) * 2);
  }
  
  .logo-letter {
    font-size: 2rem;
  }
  
  .captcha-container {
    flex-direction: column;
  }
  
  .captcha-image {
    width: 100%;
  }
}
</style> 