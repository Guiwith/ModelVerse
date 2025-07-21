/// <reference types="vite/client" />

declare module '*.vue' {
  import { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

declare module 'vue' {
  import { DefineComponent } from '@vue/runtime-dom'
  export { 
    createApp, 
    defineComponent, 
    ref, 
    reactive, 
    computed, 
    watch, 
    onMounted, 
    nextTick 
  } from '@vue/runtime-dom'
  export default DefineComponent
} 