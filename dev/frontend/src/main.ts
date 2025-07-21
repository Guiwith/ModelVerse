import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './assets/styles/theme.css'
import './assets/styles/material.css'

const app = createApp(App)
app.use(router)
app.mount('#app') 