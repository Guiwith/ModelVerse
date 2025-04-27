declare module 'vue/dist/vue.esm-bundler.js' {
  import * as Vue from 'vue'
  export * from 'vue'
  export default Vue
}

declare module '*.vue' {
  import { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
} 