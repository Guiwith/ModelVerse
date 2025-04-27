import { ref } from 'vue'

const toasts = ref<Array<{id: number, message: string, type: string, show: boolean}>>([])
let toastId = 0

export const useToast = () => {
  const showToast = (message: string, type = 'info', duration = 3000) => {
    const id = toastId++
    const toast = {
      id,
      message,
      type,
      show: true
    }
    
    toasts.value.push(toast)
    
    setTimeout(() => {
      const index = toasts.value.findIndex(t => t.id === id)
      if (index !== -1) {
        toasts.value.splice(index, 1)
      }
    }, duration)
    
    return id
  }
  
  const hideToast = (id: number) => {
    const index = toasts.value.findIndex(t => t.id === id)
    if (index !== -1) {
      toasts.value.splice(index, 1)
    }
  }
  
  return {
    toasts,
    showToast,
    hideToast
  }
} 