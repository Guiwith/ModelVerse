<template>
  <div class="not-found">
    <div class="not-found-content">
      <div class="not-found-icon">
        <span class="material-icons">search_off</span>
      </div>
      <h1>404</h1>
      <h2>页面未找到</h2>
      <p>您请求的页面不存在或已被移除</p>
      <div class="not-found-actions">
        <router-link to="/" class="btn btn-primary">
          <span class="material-icons">home</span>
          返回首页
        </router-link>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'NotFound'
})
</script>

<style scoped>
.not-found {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 80vh;
}

.not-found-content {
  text-align: center;
  max-width: 480px;
  padding: calc(var(--spacing-unit) * 3);
}

.not-found-icon {
  margin-bottom: calc(var(--spacing-unit) * 2);
}

.not-found-icon .material-icons {
  font-size: 80px;
  color: var(--primary-color);
}

.not-found h1 {
  font-size: 72px;
  font-weight: var(--font-weight-bold);
  margin: 0;
  line-height: 1;
  color: var(--primary-color);
}

.not-found h2 {
  font-size: var(--font-size-headline);
  margin: calc(var(--spacing-unit) * 2) 0;
}

.not-found p {
  margin-bottom: calc(var(--spacing-unit) * 4);
  opacity: 0.7;
}

.not-found-actions {
  display: flex;
  justify-content: center;
}

.not-found-actions .btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-unit);
}

/* 响应式调整 */
@media (max-width: 480px) {
  .not-found-icon .material-icons {
    font-size: 60px;
  }
  
  .not-found h1 {
    font-size: 60px;
  }
  
  .not-found h2 {
    font-size: var(--font-size-title);
  }
}
</style> 