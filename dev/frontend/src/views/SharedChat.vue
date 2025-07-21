<template>
  <div class="shared-chat-page">
    <div class="chat-header">
      <router-link to="/shared" class="back-link">
        <span class="material-icons">arrow_back</span>
        返回模型列表
      </router-link>
      <div class="chat-title">
        <h1>{{ task ? task.display_name : '加载中...' }}</h1>
        <div v-if="task" class="model-tag">公开共享模型</div>
      </div>
      <div class="chat-actions">
        <button @click="clearMessages" class="btn btn-secondary">
          <span class="material-icons">delete_sweep</span>
          清空对话
        </button>
      </div>
    </div>
    
    <div v-if="!task && !loading" class="error-container">
      <span class="material-icons error-icon">error</span>
      <h2>无法加载共享模型</h2>
      <p>无法找到该共享模型或模型当前不可用</p>
      <router-link to="/shared" class="btn btn-primary">返回模型列表</router-link>
    </div>
    
    <div v-else-if="task && task.status !== 'RUNNING'" class="error-container">
      <span class="material-icons warning-icon">warning</span>
      <h2>共享模型未运行</h2>
      <p>该共享模型当前不可用，请稍后再试</p>
      <router-link to="/shared" class="btn btn-primary">返回模型列表</router-link>
    </div>
    
    <div v-else class="chat-container">
      <div ref="messagesContainer" class="messages-container">
        <div class="welcome-message" v-if="messages.length === 0">
          <h2>欢迎使用 {{ task ? task.display_name : '共享模型' }}</h2>
          <p>您可以开始与模型对话，尝试问些问题或要求完成任务。</p>
          <div class="suggestions">
            <h3>对话建议</h3>
            <div class="suggestion-buttons">
              <button @click="useSuggestion('请介绍一下你自己')" class="suggestion-btn">请介绍一下你自己</button>
              <button @click="useSuggestion('写一段Python代码实现快速排序')" class="suggestion-btn">写一段Python快速排序</button>
              <button @click="useSuggestion('解释一下量子计算的基本原理')" class="suggestion-btn">解释量子计算原理</button>
              <button @click="useSuggestion('写一篇关于人工智能的短文')" class="suggestion-btn">写一篇人工智能短文</button>
            </div>
          </div>
        </div>
        
        <div v-for="(message, index) in messages" :key="index" class="message" :class="message.role">
          <div class="message-header">
            <div class="avatar" :class="message.role">
              <span class="material-icons">{{ message.role === 'user' ? 'person' : 'smart_toy' }}</span>
            </div>
            <div class="message-role">{{ message.role === 'user' ? '用户' : '助手' }}</div>
          </div>
          
          <div class="message-content" v-html="formatMessage(message.content)"></div>
          
          <div class="message-actions" v-if="message.role === 'assistant'">
            <button @click="copyMessageContent(message.content)" class="action-btn">
              <span class="material-icons">content_copy</span>
            </button>
          </div>
        </div>
        
        <div v-if="isStreaming" class="message assistant streaming">
          <div class="message-header">
            <div class="avatar assistant">
              <span class="material-icons">smart_toy</span>
            </div>
            <div class="message-role">助手</div>
          </div>
          
          <div class="message-content" v-html="formatMessage(streamingContent)"></div>
          
          <div class="streaming-indicator">
            <div class="dot"></div>
            <div class="dot"></div>
            <div class="dot"></div>
          </div>
        </div>
      </div>
      
      <div class="input-container">
        <div class="input-wrapper">
          <textarea
            ref="inputField"
            v-model="userInput"
            placeholder="输入您的消息..."
            @keydown.enter.ctrl="sendMessage"
            @keydown.enter.meta="sendMessage"
            rows="1"
            :disabled="isStreaming"
          ></textarea>
          
          <button @click="sendMessage" class="send-btn" :disabled="!canSendMessage">
            <span class="material-icons">{{ isStreaming ? 'stop' : 'send' }}</span>
          </button>
        </div>
        
        <div class="input-help">
          按 <kbd>Ctrl</kbd> + <kbd>Enter</kbd> 发送消息
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { sharedApiClient, sharedInference } from '../api/client'
import { useToast } from '../composables/toast'
import { getApiBaseUrl } from '../config'
import * as marked from 'marked'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js'

// 配置Marked和Highlight.js
marked.marked.setOptions({
  highlight: function(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(code, { language: lang }).value
      } catch (e) {}
    }
    return hljs.highlightAuto(code).value
  }
})

export default {
  name: 'SharedChat',
  setup() {
    const route = useRoute()
    const router = useRouter()
    const { showToast } = useToast()
    
    // 引用
    const messagesContainer = ref(null)
    const inputField = ref(null)
    
    // 状态
    const taskId = parseInt(route.params.id)
    const task = ref(null)
    const loading = ref(true)
    const isStreaming = ref(false)
    const streamingContent = ref('')
    const userInput = ref('')
    const messages = reactive([])
    
    // WebSocket连接
    let ws = null
    
    // 刷新定时器
    let refreshTimer = null
    
    // 计算属性
    const canSendMessage = computed(() => {
      return userInput.value.trim() !== '' && !isStreaming.value
    })
    
    // 加载任务详情
    const loadTask = async () => {
      try {
        loading.value = true
        const response = await sharedInference.getTask(taskId)
        task.value = response.data
        
        if (task.value) {
          // 如果任务正在运行，则连接WebSocket
          if (task.value.status === 'RUNNING') {
            connectWebSocket()
          }
        }
      } catch (error) {
        console.error('加载共享模型失败:', error)
        showToast('加载共享模型失败: ' + (error.response?.data?.detail || error.message), 'error')
        task.value = null
      } finally {
        loading.value = false
      }
    }
    
    // 连接WebSocket
    const connectWebSocket = () => {
      // 如果已经有连接，先关闭
      disconnectWebSocket()
      
      // 建立新的WebSocket连接
      const apiBaseUrl = getApiBaseUrl();
      const url = new URL(apiBaseUrl);
      const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
      
      // 直接使用API的WebSocket路径
      try {
        ws = new WebSocket(`${protocol}//${url.host}/api/ws/chat/${taskId}`)
        
        ws.onopen = () => {
          console.log('WebSocket连接已建立')
        }
        
        ws.onerror = (error) => {
          console.error('WebSocket连接错误:', error)
          showToast('WebSocket连接错误，请尝试刷新页面', 'error')
        }
        
        setupWebSocketHandlers()
      } catch (e) {
        console.error('WebSocket连接错误:', e)
        showToast('WebSocket连接错误，请尝试刷新页面', 'error')
      }
    }
    
    // 设置WebSocket事件处理
    const setupWebSocketHandlers = () => {
      if (!ws) return
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          console.log('WebSocket收到消息:', data);
          
          if (data.type === 'stream') {
            handleStreamMessage(data)
          } else if (data.type === 'end') {
            handleEndMessage(data)
          } else if (data.type === 'error') {
            handleErrorMessage(data)
          } else if (data.type === 'connected') {
            console.log('已连接到共享模型:', data.model_name);
          } else if (data.type === 'pong') {
            console.log('收到pong响应');
          }
        } catch (error) {
          console.error('处理WebSocket消息失败:', error)
        }
      }
      
      ws.onclose = () => {
        console.log('WebSocket连接已关闭')
      }
    }
    
    // 断开WebSocket连接
    const disconnectWebSocket = () => {
      if (ws) {
        ws.close()
        ws = null
      }
    }
    
    // 处理流式消息
    const handleStreamMessage = (data) => {
      if (!isStreaming.value) {
        isStreaming.value = true
        streamingContent.value = ''
      }
      
      streamingContent.value += data.content
      scrollToBottom()
    }
    
    // 处理消息结束
    const handleEndMessage = (data) => {
      if (isStreaming.value) {
        isStreaming.value = false
        
        // 添加完整的助手回复
        messages.push({
          role: 'assistant',
          content: data.content
        })
        
        streamingContent.value = ''
        scrollToBottom()
      }
    }
    
    // 处理错误消息
    const handleErrorMessage = (data) => {
      isStreaming.value = false
      showToast(`模型响应错误: ${data.error}`, 'error')
    }
    
    // 格式化消息内容（支持Markdown和思考标签）
    const formatMessage = (content) => {
      if (!content) return ''
      
      // 处理思考标签
      let processedContent = content.replace(
        /<think>([\s\S]*?)<\/think>/g,
        '<div class="thinking-section"><div class="thinking-header"><span class="material-icons">psychology</span>思考过程</div><div class="thinking-content">$1</div></div>'
      )
      
      // 使用marked解析Markdown
      const html = marked.marked(processedContent)
      
      // 使用DOMPurify清理HTML，允许thinking相关的class
      return DOMPurify.sanitize(html, {
        ADD_ATTR: ['class'],
        ADD_TAGS: ['div', 'span']
      })
    }
    
    // 滚动到底部
    const scrollToBottom = () => {
      nextTick(() => {
        if (messagesContainer.value) {
          messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
        }
      })
    }
    
    // 自动调整文本域高度
    const resizeTextarea = () => {
      if (inputField.value) {
        inputField.value.style.height = 'auto'
        inputField.value.style.height = inputField.value.scrollHeight + 'px'
      }
    }
    
    // 使用建议
    const useSuggestion = (text) => {
      userInput.value = text
      resizeTextarea()
    }
    
    // 发送消息
    const sendMessage = async () => {
      const message = userInput.value.trim()
      
      if (!message || isStreaming.value) return
      
      // 添加用户消息到消息列表
      messages.push({
        role: 'user',
        content: message
      })
      
      // 清空输入框
      userInput.value = ''
      
      // 自动调整高度
      resizeTextarea()
      
      // 滚动到底部
      scrollToBottom()
      
      // 调整WebSocket的状态，准备开始流式响应
      isStreaming.value = true
      streamingContent.value = ''
      
      // 发送消息到服务器
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: 'message',
          content: message
        }))
      } else {
        showToast('WebSocket连接已断开，正在尝试重新连接', 'warning')
        connectWebSocket()
        setTimeout(() => {
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
              type: 'message',
              content: message
            }))
          } else {
            showToast('无法连接到服务器，请刷新页面重试', 'error')
            isStreaming.value = false
          }
        }, 1000)
      }
    }
    
    // 清空消息
    const clearMessages = () => {
      if (messages.length === 0) return
      
      messages.splice(0, messages.length)
      
      // 通知服务器清空对话历史
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: 'clear_history'
        }))
      }
      
      showToast('对话已清空', 'success')
    }
    
    // 复制消息内容
    const copyMessageContent = (content) => {
      navigator.clipboard.writeText(content)
        .then(() => showToast('已复制到剪贴板', 'success'))
        .catch(() => showToast('复制失败，请手动选择并复制', 'error'))
    }
    
    // 发送心跳
    const sendHeartbeat = () => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      }
    }
    
    // 启动心跳定时器
    const startHeartbeat = () => {
      refreshTimer = setInterval(sendHeartbeat, 30000) // 每30秒发送一次心跳
    }
    
    // 监听输入框变化，自动调整高度
    watch(userInput, () => {
      resizeTextarea()
    })
    
    // 生命周期钩子
    onMounted(() => {
      loadTask()
      startHeartbeat()
      resizeTextarea()
    })
    
    onUnmounted(() => {
      disconnectWebSocket()
      clearInterval(refreshTimer)
    })
    
    return {
      task,
      loading,
      isStreaming,
      streamingContent,
      userInput,
      messages,
      messagesContainer,
      inputField,
      canSendMessage,
      formatMessage,
      sendMessage,
      clearMessages,
      copyMessageContent,
      useSuggestion
    }
  }
}
</script>

<style scoped>
.shared-chat-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: var(--background-color);
}

.chat-header {
  display: flex;
  align-items: center;
  padding: 1rem 2rem;
  background-color: var(--surface-color);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  z-index: 10;
}

.back-link {
  display: flex;
  align-items: center;
  color: var(--text-primary);
  text-decoration: none;
  margin-right: 2rem;
  padding: 0.5rem;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.back-link:hover {
  background-color: var(--hover-color);
}

.back-link .material-icons {
  margin-right: 0.5rem;
}

.chat-title {
  flex: 1;
}

.chat-title h1 {
  font-size: 1.5rem;
  margin: 0;
  margin-bottom: 0.25rem;
  color: var(--text-primary);
}

.model-tag {
  display: inline-block;
  background-color: var(--primary-light);
  color: var(--primary-dark);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 500;
}

.chat-actions {
  display: flex;
  gap: 0.5rem;
}

.btn {
  display: flex;
  align-items: center;
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 4px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
}

.btn-secondary {
  background-color: var(--surface-variant-color);
  color: var(--on-surface-variant);
}

.btn-secondary:hover {
  background-color: var(--hover-color);
}

.btn-primary {
  background-color: var(--primary);
  color: var(--on-primary);
}

.btn-primary:hover {
  background-color: var(--primary-dark);
}

.btn .material-icons {
  margin-right: 0.5rem;
}

.error-container,
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  height: 100%;
  padding: 2rem;
}

.error-icon,
.warning-icon {
  font-size: 4rem;
  margin-bottom: 1rem;
}

.error-icon {
  color: var(--error);
}

.warning-icon {
  color: var(--warning);
}

.error-container h2 {
  font-size: 1.8rem;
  margin-bottom: 1rem;
  color: var(--text-primary);
}

.error-container p {
  font-size: 1.1rem;
  margin-bottom: 2rem;
  color: var(--text-secondary);
}

.chat-container {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 2rem;
}

.welcome-message {
  background-color: var(--surface-color);
  border-radius: 10px;
  padding: 2rem;
  margin-bottom: 2rem;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
  text-align: center;
}

.welcome-message h2 {
  font-size: 1.8rem;
  margin-bottom: 1rem;
  color: var(--text-primary);
}

.welcome-message p {
  font-size: 1.1rem;
  margin-bottom: 2rem;
  color: var(--text-secondary);
}

.suggestions h3 {
  font-size: 1.2rem;
  margin-bottom: 1rem;
  color: var(--text-primary);
}

.suggestion-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 0.8rem;
  justify-content: center;
}

.suggestion-btn {
  background-color: var(--surface-variant-color);
  border: 1px solid var(--divider-color);
  border-radius: 20px;
  padding: 0.6rem 1.2rem;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
  color: var(--text-primary);
}

.suggestion-btn:hover {
  background-color: var(--hover-color);
  transform: translateY(-2px);
}

.message {
  margin-bottom: 1.5rem;
  display: flex;
  flex-direction: column;
}

.message.user {
  margin-left: auto;
  max-width: 80%;
}

.message.assistant {
  margin-right: auto;
  max-width: 80%;
}

.message-header {
  display: flex;
  align-items: center;
  margin-bottom: 0.5rem;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 0.5rem;
}

.avatar.user {
  background-color: var(--primary-light);
  color: var(--primary-dark);
}

.avatar.assistant {
  background-color: var(--surface-variant-color);
  color: var(--on-surface-variant);
}

.message-role {
  font-weight: 500;
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.message-content {
  background-color: var(--surface-color);
  border-radius: 10px;
  padding: 1rem;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
  word-break: break-word;
  color: var(--text-primary);
}

.message.user .message-content {
  background-color: var(--primary-light);
  color: var(--primary-dark);
}

.message-content :deep(pre) {
  background-color: var(--code-background);
  border-radius: 5px;
  padding: 1rem;
  overflow-x: auto;
  margin: 1rem 0;
}

.message-content :deep(code) {
  font-family: monospace;
  background-color: var(--code-background);
  padding: 0.2rem 0.4rem;
  border-radius: 3px;
}

.message-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 1rem 0;
}

.message-content :deep(th),
.message-content :deep(td) {
  border: 1px solid var(--divider-color);
  padding: 0.5rem;
}

.message-content :deep(th) {
  background-color: var(--surface-variant-color);
}

.message-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 0.5rem;
}

.action-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0.3rem;
  border-radius: 50%;
  transition: background-color 0.2s;
}

.action-btn:hover {
  background-color: var(--hover-color);
}

.action-btn .material-icons {
  font-size: 16px;
}

.streaming-indicator {
  display: flex;
  align-items: center;
  margin-top: 0.5rem;
  padding-left: 1rem;
}

.streaming-indicator .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--text-secondary);
  margin-right: 4px;
  animation: pulse 1s infinite;
}

.streaming-indicator .dot:nth-child(2) {
  animation-delay: 0.2s;
}

.streaming-indicator .dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes pulse {
  0% {
    transform: scale(0.8);
    opacity: 0.5;
  }
  50% {
    transform: scale(1.2);
    opacity: 1;
  }
  100% {
    transform: scale(0.8);
    opacity: 0.5;
  }
}

.input-container {
  background-color: var(--surface-color);
  padding: 1rem 2rem 2rem;
  border-top: 1px solid var(--divider-color);
}

.input-wrapper {
  display: flex;
  position: relative;
  border: 1px solid var(--divider-color);
  border-radius: 10px;
  background-color: var(--surface-color);
  transition: border-color 0.2s;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
}

.input-wrapper:focus-within {
  border-color: var(--primary);
}

textarea {
  flex: 1;
  border: none;
  padding: 1rem;
  resize: none;
  font-family: inherit;
  font-size: 1rem;
  min-height: 46px;
  max-height: 200px;
  background: transparent;
  outline: none;
  border-radius: 10px;
  color: var(--text-primary);
}

.send-btn {
  background-color: var(--primary);
  color: var(--on-primary);
  border: none;
  width: 46px;
  height: 46px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.2s;
  margin: 4px;
  flex-shrink: 0;
}

.send-btn:disabled {
  background-color: var(--disabled);
  cursor: not-allowed;
}

.send-btn:not(:disabled):hover {
  background-color: var(--primary-dark);
}

.input-help {
  margin-top: 0.5rem;
  text-align: right;
  font-size: 0.8rem;
  color: var(--text-secondary);
}

kbd {
  background-color: var(--surface-variant-color);
  border: 1px solid var(--divider-color);
  border-radius: 3px;
  padding: 0.1rem 0.3rem;
  font-size: 0.7rem;
  color: var(--text-primary);
}

/* 思考部分样式 */
.message-content :deep(.thinking-section) {
  background-color: var(--surface-variant-color);
  border: 1px solid var(--divider-color);
  border-radius: 8px;
  margin: 1rem 0;
  overflow: hidden;
}

.message-content :deep(.thinking-header) {
  display: flex;
  align-items: center;
  padding: 0.5rem 0.75rem;
  background-color: var(--primary-light);
  color: var(--primary-dark);
  font-weight: 500;
  font-size: 0.9rem;
  border-bottom: 1px solid var(--divider-color);
}

.message-content :deep(.thinking-header .material-icons) {
  font-size: 16px;
  margin-right: 0.5rem;
}

.message-content :deep(.thinking-content) {
  padding: 0.75rem;
  background-color: var(--background-color);
  color: var(--text-secondary);
  font-style: italic;
  line-height: 1.5;
  border-left: 3px solid var(--primary-light);
}

.message-content :deep(.thinking-content p) {
  margin: 0.5rem 0;
}

.message-content :deep(.thinking-content p:first-child) {
  margin-top: 0;
}

.message-content :deep(.thinking-content p:last-child) {
  margin-bottom: 0;
}
</style> 