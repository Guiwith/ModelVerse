declare module 'vue-router' {
  export function createRouter(options: any): any
  export function createWebHistory(): any
  export function useRouter(): any
  export function useRoute(): any
  
  export interface RouteLocationNormalized {
    path: string
    fullPath: string
    query: Record<string, string | string[]>
    params: Record<string, string>
    name: string | null | undefined
    meta: Record<string, any>
    matched: any[]
  }
  
  export interface RouteLocationRaw {
    name?: string
    path?: string
    query?: Record<string, string | string[]>
    params?: Record<string, string>
  }
  
  export type NavigationGuardNext = (to?: RouteLocationRaw | false | null) => void
} 