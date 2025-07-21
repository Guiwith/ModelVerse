declare module 'vue-router' {
  import { RouteRecordRaw } from 'vue-router/dist/vue-router'
  
  export function createRouter(options: any): any
  export function createWebHistory(): any
  export { RouteRecordRaw }
} 