/**
 * 环境检测和配置工具
 */

/**
 * 获取当前主机的IP地址或域名
 */
export const getCurrentHost = (): string => {
  return window.location.hostname;
}

/**
 * 获取当前协议 (http/https)
 */
export const getCurrentProtocol = (): string => {
  return window.location.protocol;
}

/**
 * 根据环境自动检测API基础URL
 */
export const getApiBaseUrl = (): string => {
  // 首先检查是否有环境变量（Vite环境变量）
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  
  // 如果没有环境变量，根据当前主机自动构建
  const protocol = getCurrentProtocol();
  const host = getCurrentHost();
  
  // 开发环境检测
  if (host === 'localhost' || host === '127.0.0.1' || host.startsWith('192.168') || host.startsWith('10.')) {
    return `${protocol}//${host}:8888`;
  }
  
  // 生产环境或其他情况，使用当前主机的8888端口
  return `${protocol}//${host}:8888`;
}

/**
 * 环境配置类型
 */
export interface EnvConfig {
  apiBaseUrl: string;
  apiHost: string;
  apiPort: number;
  isDevelopment: boolean;
  isProduction: boolean;
}

/**
 * 获取完整的环境配置
 */
export const getEnvConfig = (): EnvConfig => {
  const apiBaseUrl = getApiBaseUrl();
  const url = new URL(apiBaseUrl);
  
  return {
    apiBaseUrl,
    apiHost: url.hostname,
    apiPort: parseInt(url.port) || 8888,
    isDevelopment: import.meta.env.DEV || false,
    isProduction: import.meta.env.PROD || false
  };
}

/**
 * 检查API服务器是否可达
 */
export const checkApiHealth = async (): Promise<boolean> => {
  try {
    const response = await fetch(`${getApiBaseUrl()}/health`, {
      method: 'GET',
      timeout: 5000
    });
    return response.ok;
  } catch (error) {
    console.warn('API health check failed:', error);
    return false;
  }
} 