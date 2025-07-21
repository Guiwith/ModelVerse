import { ref, watch, onMounted } from 'vue'

// 主题类型
export type ThemeType = 'light' | 'dark'

// 主题存储的本地存储键
const THEME_KEY = 'app_theme'

// 创建全局状态
const currentTheme = ref<ThemeType>('light')

export function useTheme() {
  // 初始化主题
  const initTheme = () => {
    // 从本地存储中获取保存的主题
    const savedTheme = localStorage.getItem(THEME_KEY) as ThemeType | null
    
    // 如果有保存的主题，使用保存的主题
    if (savedTheme && ['light', 'dark'].includes(savedTheme)) {
      currentTheme.value = savedTheme
    } else {
      // 如果没有保存的主题，检查系统偏好
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      currentTheme.value = prefersDark ? 'dark' : 'light'
    }
    
    // 应用主题
    applyTheme(currentTheme.value)
  }
  
  // 切换主题
  const toggleTheme = () => {
    const newTheme: ThemeType = currentTheme.value === 'light' ? 'dark' : 'light'
    setTheme(newTheme)
  }
  
  // 设置特定主题
  const setTheme = (theme: ThemeType) => {
    currentTheme.value = theme
    localStorage.setItem(THEME_KEY, theme)
    applyTheme(theme)
  }
  
  // 应用主题到DOM
  const applyTheme = (theme: ThemeType) => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark-theme')
    } else {
      document.documentElement.classList.remove('dark-theme')
    }
  }
  
  // 监听系统主题变化
  onMounted(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    
    // 初始化主题
    initTheme()
    
    // 监听系统主题变化
    mediaQuery.addEventListener('change', (e) => {
      // 只有当用户没有明确设置主题时才跟随系统变化
      if (!localStorage.getItem(THEME_KEY)) {
        const newTheme: ThemeType = e.matches ? 'dark' : 'light'
        setTheme(newTheme)
      }
    })
  })
  
  return {
    currentTheme,
    toggleTheme,
    setTheme
  }
} 