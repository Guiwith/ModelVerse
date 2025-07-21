// 添加类型声明
declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean;
    requiresAdmin?: boolean;
    guest?: boolean;
  }
}

import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Login from '../views/Login.vue'
import Register from '../views/Register.vue'
import Profile from '../views/Profile.vue'
import Admin from '../views/Admin.vue'
import NotFound from '../views/NotFound.vue'
import Resources from '../views/Resources.vue'
import Training from '../views/Training.vue'
import TrainingDetail from '../views/TrainingDetail.vue'
import Privacy from '../views/Privacy.vue'
import About from '../views/About.vue'
import Inference from '../views/Inference.vue'
import InferenceDetail from '../views/InferenceDetail.vue'
import ChatPage from '../views/ChatPage.vue'
import SharedChat from '../views/SharedChat.vue'
import SharedChatList from '../views/SharedChatList.vue'
import Evaluation from '../views/Evaluation.vue'
import EvaluationDetail from '../views/EvaluationDetail.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home,
    meta: { requiresAuth: true }
  },
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { guest: true }
  },
  {
    path: '/register',
    name: 'Register',
    component: Register,
    meta: { guest: true }
  },
  {
    path: '/profile',
    name: 'Profile',
    component: Profile,
    meta: { requiresAuth: true }
  },
  {
    path: '/resources',
    name: 'Resources',
    component: Resources,
    meta: { requiresAuth: true }
  },
  {
    path: '/training',
    name: 'Training',
    component: Training,
    meta: { requiresAuth: true }
  },
  {
    path: '/training/:id',
    name: 'TrainingDetail',
    component: TrainingDetail,
    meta: { requiresAuth: true }
  },
  {
    path: '/inference',
    name: 'Inference',
    component: Inference,
    meta: { requiresAuth: true }
  },
  {
    path: '/inference/:id',
    name: 'InferenceDetail',
    component: InferenceDetail,
    meta: { requiresAuth: true }
  },
  {
    path: '/chat/:id',
    name: 'Chat',
    component: ChatPage,
    meta: { requiresAuth: true }
  },
  {
    path: '/evaluation',
    name: 'Evaluation',
    component: Evaluation,
    meta: { requiresAuth: true }
  },
  {
    path: '/evaluation/:id',
    name: 'EvaluationDetail',
    component: EvaluationDetail,
    meta: { requiresAuth: true }
  },
  {
    path: '/shared',
    name: 'SharedChatList',
    component: SharedChatList
  },
  {
    path: '/shared/:id',
    name: 'SharedChat',
    component: SharedChat
  },
  {
    path: '/admin',
    name: 'Admin',
    component: Admin,
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/privacy',
    name: 'Privacy',
    component: Privacy
  },
  {
    path: '/about',
    name: 'About',
    component: About
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: NotFound
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 导航守卫
router.beforeEach((to: any, _: any, next: any) => {
  // 检查本地存储中的令牌
  const token = localStorage.getItem('auth_token')
  const userInfo = localStorage.getItem('user_info')
  const isLoggedIn = token && userInfo
  
  // 是否是管理员
  let isAdmin = false
  if (isLoggedIn && userInfo) {
    try {
      const user = JSON.parse(userInfo)
      isAdmin = user.is_admin === true
    } catch (e) {
      console.error('解析用户信息失败:', e)
    }
  }
  
  // 路由需要验证
  if (to.matched.some((record: any) => record.meta.requiresAuth)) {
    if (!isLoggedIn) {
      next({ name: 'Login', query: { redirect: to.fullPath } })
    } else if (to.matched.some((record: any) => record.meta.requiresAdmin) && !isAdmin) {
      // 路由需要管理员权限
      next({ name: 'Home' })
    } else {
      next()
    }
  } else if (to.matched.some((record: any) => record.meta.guest) && isLoggedIn) {
    // 已登录用户不能访问访客页面（如登录页）
    next({ name: 'Home' })
  } else {
    next()
  }
})

export default router 