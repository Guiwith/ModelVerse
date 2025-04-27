/**
 * 应用全局配置
 */

// 动态获取API基础URL
export const getApiBaseUrl = (): string => {
  // 临时使用固定IP地址，后续优化
  return 'http://172.31.118.255:8000' 
}

// 应用配置
export const config = {
  appName: 'ModelVerse',
  apiBasePath: '/api',
  staticBasePath: '/static',
  
  // 存储键
  storageKeys: {
    authToken: 'auth_token',
    userInfo: 'user_info',
    theme: 'app_theme'
  },
  
  // 默认分页大小
  defaultPageSize: 10,
  
  // 应用主题配置
  themes: {
    light: 'light',
    dark: 'dark',
    system: 'system'
  }
} 