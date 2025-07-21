/**
 * 应用全局配置
 */

import { getApiBaseUrl as getEnvApiBaseUrl } from './utils/env'

// 动态获取API基础URL
export const getApiBaseUrl = (): string => {
  return getEnvApiBaseUrl()
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