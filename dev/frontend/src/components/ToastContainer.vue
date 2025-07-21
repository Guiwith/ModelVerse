<template>
  <div class="toast-container">
    <transition-group name="toast">
      <div 
        v-for="toast in toasts" 
        :key="toast.id" 
        class="toast" 
        :class="toast.type"
      >
        {{ toast.message }}
        <button class="toast-close" @click="hideToast(toast.id)">×</button>
      </div>
    </transition-group>
  </div>
</template>

<script>
import { useToast } from '../composables/toast'

export default {
  name: 'ToastContainer',
  setup() {
    const { toasts, hideToast } = useToast()
    
    return {
      toasts,
      hideToast
    }
  }
}
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 300px;
}

.toast {
  padding: 12px 16px;
  border-radius: 4px;
  background-color: #333;
  color: white;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
  animation: slideIn 0.3s ease-out;
  position: relative;
  opacity: 0.9;
}

.toast-close {
  position: absolute;
  top: 8px;
  right: 8px;
  background: none;
  border: none;
  color: white;
  font-size: 18px;
  cursor: pointer;
  opacity: 0.7;
}

.toast-close:hover {
  opacity: 1;
}

.toast.info {
  background-color: #2196F3;
}

.toast.success {
  background-color: #4CAF50;
}

.toast.warning {
  background-color: #FF9800;
}

.toast.error {
  background-color: #F44336;
}

/* 动画 */
.toast-enter-from {
  transform: translateX(100%);
  opacity: 0;
}

.toast-enter-active {
  transition: all 0.3s ease-out;
}

.toast-leave-active {
  transition: all 0.3s ease-in;
}

.toast-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 0.9;
  }
}
</style> 