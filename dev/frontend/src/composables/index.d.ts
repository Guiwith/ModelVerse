declare module './auth' {
  import { Ref } from 'vue'
  import { User } from '../types/models'
  
  export function useAuth(): {
    isLoggedIn: Ref<boolean>;
    isAdmin: Ref<boolean>;
    user: Ref<User | null>;
    error: Ref<string>;
    login: (username: string, password: string) => Promise<boolean>;
    logout: () => void;
    checkAuth: () => Promise<boolean>;
    getUserInfo: () => Promise<any>;
    getAuthHeaders: () => Record<string, string>;
  }
}

declare module './api' {
  export function useApi(): {
    getUsers: () => Promise<any[]>;
    createUser: (userData: any) => Promise<any>;
    getAdminDashboard: () => Promise<any>;
    getItems: () => Promise<string[]>;
  }
}

declare module './theme' {
  import { Ref } from 'vue'
  
  export type ThemeType = 'light' | 'dark'
  
  export function useTheme(): {
    currentTheme: Ref<ThemeType>;
    toggleTheme: () => void;
    setTheme: (theme: ThemeType) => void;
  }
} 