<template>
  <div class="chat-page">
    <div class="chat-header">
      <router-link :to="`/inference/${taskId}`" class="back-link">
        <span class="material-icons">arrow_back</span>
        返回推理任务
      </router-link>
      <div class="chat-title">
        <h1>{{ task ? task.name : '加载中...' }}</h1>
        <div v-if="task" class="model-name">模型: {{ modelName }}</div>
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
      <h2>无法加载推理任务</h2>
      <p>无法找到ID为 {{ taskId }} 的推理任务或您没有权限访问</p>
      <router-link to="/inference" class="btn btn-primary">返回推理任务列表</router-link>
    </div>
    
    <div v-else-if="task && task.status !== 'RUNNING'" class="error-container">
      <span class="material-icons warning-icon">warning</span>
      <h2>推理任务未运行</h2>
      <p>推理任务当前状态为: {{ getStatusText(task.status) }}</p>
      <p>请先启动推理任务后再进行聊天</p>
      <router-link :to="`/inference/${taskId}`" class="btn btn-primary">返回管理推理任务</router-link>
    </div>
    
    <div v-else class="chat-container">
      <div ref="messagesContainer" class="messages-container">
        <div class="welcome-message" v-if="messages.length === 0">
          <h2>欢迎使用 {{ task ? task.name : '大语言模型' }}</h2>
          <p>您可以开始与模型对话，尝试问些问题或要求完成任务。</p>
          <div class="suggestions">
            <h3>对话建议</h3>
            <div class="suggestion-buttons">
              <button @click="useSuggestion('请介绍一下你自己')" class="suggestion-btn">请介绍一下你自己</button>
              <button @click="useSuggestion('我想让你帮我写一段Python代码来分析CSV文件')" class="suggestion-btn">帮我写Python代码分析CSV</button>
              <button @click="useSuggestion('解释一下量子计算的基本原理')" class="suggestion-btn">解释量子计算原理</button>
              <button @click="useSuggestion('写一篇关于可持续发展的短文')" class="suggestion-btn">写一篇可持续发展短文</button>
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
import { apiClient, inference } from '../api/client'
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
  name: 'ChatPage',
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
    const model = ref(null)
    const loading = ref(true)
    const isStreaming = ref(false)
    const streamingContent = ref('')
    const userInput = ref('')
    const messages = reactive([])
    const messageLogs = ref([]) // 调试用的消息日志
    
    // WebSocket连接
    let ws = null
    
    // 刷新定时器
    let refreshTimer = null
    
    // 计算属性
    const modelName = computed(() => {
      if (!model.value) return '大语言模型'
      return model.value.name
    })
    
    const canSendMessage = computed(() => {
      return userInput.value.trim() !== '' && !isStreaming.value
    })
    
    // 加载任务详情
    const loadTask = async () => {
      try {
        loading.value = true
        const response = await inference.getTask(taskId)
        task.value = response.data
        
        if (task.value) {
          // 加载模型信息
          await loadModel(task.value.model_id)
          
          // 如果任务正在运行，则连接WebSocket
          if (task.value.status === 'RUNNING') {
            connectWebSocket()
          }
        }
      } catch (error) {
        console.error('加载推理任务失败:', error)
        showToast('加载推理任务失败: ' + (error.response?.data?.detail || error.message), 'error')
        task.value = null
      } finally {
        loading.value = false
      }
    }
    
    // 加载模型信息
    const loadModel = async (modelId) => {
      try {
        const response = await apiClient.get(`/api/resources/${modelId}`)
        model.value = response.data
      } catch (error) {
        console.error('加载模型信息失败:', error)
        model.value = null
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
      
      // 获取认证令牌
      const token = localStorage.getItem('token')
      
      // 将token作为查询参数添加到WebSocket URL
      const wsUrl = `${protocol}//${url.host}/api/ws/chat/${taskId}${token ? `?token=${token}` : ''}`
      
      ws = new WebSocket(wsUrl)
      
      ws.onopen = () => {
        console.log('WebSocket连接已建立')
      }
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          // 添加到消息日志
          messageLogs.value.push({
            time: new Date().toISOString(),
            data: JSON.parse(JSON.stringify(data))
          })
          // 最多保留20条日志
          if (messageLogs.value.length > 20) {
            messageLogs.value.shift()
          }
          
          console.log('WebSocket收到消息:', data);
          
          if (data.type === 'stream') {
            handleStreamMessage(data)
          } else if (data.type === 'end') {
            handleEndMessage(data)
          } else if (data.type === 'error') {
            handleErrorMessage(data)
          } else if (data.type === 'connected') {
            console.log('已连接到推理服务:', data.model_name);
          } else if (data.type === 'pong') {
            console.log('收到pong响应');
          }
        } catch (error) {
          console.error('处理WebSocket消息失败:', error)
        }
      }
      
      ws.onerror = (error) => {
        console.error('WebSocket错误:', error)
        showToast('WebSocket连接错误，请尝试刷新页面', 'error')
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
      try {
        if (!isStreaming.value) {
          // 第一次收到流式消息，初始化状态
          isStreaming.value = true;
          streamingContent.value = data.content || '';
        } else {
          // 添加新的内容片段
          streamingContent.value += data.content || '';
        }
        
        console.log('流式内容更新:', streamingContent.value.length);
        
        // 滚动到底部
        scrollToBottom();
      } catch (error) {
        console.error('处理流式消息时出错:', error);
      }
    }
    
    // 处理结束消息
    const handleEndMessage = (data) => {
      // 添加完整的消息到消息列表
      messages.push({
        role: 'assistant',
        content: data.content
      });
      
      // 重置状态
      isStreaming.value = false;
      streamingContent.value = '';
      
      // 滚动到底部
      scrollToBottom();
      
      // 重新聚焦到输入框
      focusInputField();
      
      console.log('收到结束消息:', data);
    }
    
    // 处理错误消息
    const handleErrorMessage = (data) => {
      showToast('模型响应错误: ' + (data.error || '未知错误'), 'error')
      
      // 重置状态
      isStreaming.value = false
      streamingContent.value = ''
      
      // 重新聚焦到输入框
      focusInputField()
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
      // 检查Clipboard API是否可用
      if (navigator.clipboard && navigator.clipboard.writeText) {
        // 使用现代Clipboard API
        navigator.clipboard.writeText(content)
          .then(() => showToast('已复制到剪贴板', 'success'))
          .catch((err) => {
            console.error('复制失败:', err);
            fallbackCopy(content);
          });
      } else {
        // 降级方案
        fallbackCopy(content);
      }
    }
    
    // 降级复制方法
    const fallbackCopy = (text) => {
      try {
        // 创建临时文本区域
        const textArea = document.createElement('textarea');
        textArea.value = text;
        
        // 确保元素不可见
        textArea.style.position = 'fixed';
        textArea.style.left = '-9999px';
        textArea.style.top = '0';
        
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        // 尝试复制
        const successful = document.execCommand('copy');
        document.body.removeChild(textArea);
        
        if (successful) {
          showToast('已复制到剪贴板', 'success');
        } else {
          showToast('复制失败，请手动复制', 'error');
        }
      } catch (err) {
        console.error('降级复制失败:', err);
        showToast('复制失败，请手动复制', 'error');
      }
    }
    
    // 使用对话建议
    const useSuggestion = (suggestion) => {
      userInput.value = suggestion
      sendMessage()
    }
    
    // 滚动到底部
    const scrollToBottom = () => {
      nextTick(() => {
        if (messagesContainer.value) {
          messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
        }
      })
    }
    
    // 聚焦到输入框
    const focusInputField = () => {
      nextTick(() => {
        if (inputField.value) {
          inputField.value.focus()
        }
      })
    }
    
    // 调整textarea高度
    const resizeTextarea = () => {
      if (!inputField.value) return
      
      // 重置高度
      inputField.value.style.height = 'auto'
      
      // 设置新高度
      const newHeight = Math.min(inputField.value.scrollHeight, 200)
      inputField.value.style.height = `${newHeight}px`
    }
    
    // 格式化消息内容，转换Markdown为HTML
    const formatMessage = (content) => {
      if (!content) return ''
      
      // 使用marked解析Markdown
      const htmlContent = marked.marked(content)
      
      // 使用DOMPurify清理HTML
      return DOMPurify.sanitize(htmlContent)
    }
    
    // 获取状态文本
    const getStatusText = (status) => {
      const statusMap = {
        'CREATING': '创建中',
        'RUNNING': '运行中',
        'STOPPED': '已停止',
        'FAILED': '失败'
      }
      return statusMap[status] || status
    }
    
    // 监听输入框变化，自动调整高度
    watch(userInput, () => {
      resizeTextarea()
    })
    
    // 生命周期钩子
    onMounted(async () => {
      await loadTask()
      
      // 聚焦到输入框
      focusInputField()
      
      // 设置定时刷新
      refreshTimer = setInterval(async () => {
        // 如果任务不是运行状态，需要定期检查状态
        if (task.value && task.value.status !== 'RUNNING') {
          try {
            const response = await inference.getTask(taskId)
            task.value = response.data
            
            // 如果状态已变为运行，连接WebSocket
            if (task.value.status === 'RUNNING' && (!ws || ws.readyState !== WebSocket.OPEN)) {
              connectWebSocket()
            }
          } catch (error) {
            console.error('刷新任务状态失败:', error)
          }
        }
      }, 5000)
    })
    
    onUnmounted(() => {
      // 关闭WebSocket连接
      disconnectWebSocket()
      
      // 清除定时器
      if (refreshTimer) {
        clearInterval(refreshTimer)
      }
    })
    
    return {
      taskId,
      task,
      modelName,
      loading,
      messages,
      userInput,
      isStreaming,
      streamingContent,
      messagesContainer,
      inputField,
      sendMessage,
      clearMessages,
      copyMessageContent,
      useSuggestion,
      formatMessage,
      getStatusText,
      canSendMessage,
      messageLogs // 导出消息日志
    }
  }
}
</script>

<style scoped>
.chat-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.chat-header {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid var(--divider-color);
  background-color: var(--surface-color);
  position: sticky;
  top: 0;
  z-index: 10;
}

.back-link {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--primary);
  text-decoration: none;
  margin-right: 16px;
}

.chat-title {
  flex: 1;
}

.chat-title h1 {
  font-size: 18px;
  margin: 0;
  font-weight: 500;
}

.model-name {
  font-size: 14px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.chat-actions {
  display: flex;
  gap: 8px;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: var(--background-color);
  overflow: hidden;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  scroll-behavior: smooth;
}

.welcome-message {
  text-align: center;
  max-width: 600px;
  margin: 40px auto;
  padding: 24px;
  background-color: var(--surface-variant-color);
  border-radius: 16px;
}

.welcome-message h2 {
  margin-top: 0;
  font-size: 20px;
  font-weight: 500;
}

.suggestions {
  margin-top: 24px;
  text-align: left;
}

.suggestions h3 {
  font-size: 16px;
  margin-bottom: 12px;
  font-weight: 500;
}

.suggestion-buttons {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 8px;
}

.suggestion-btn {
  background-color: var(--surface-color);
  border: 1px solid var(--divider-color);
  border-radius: 8px;
  padding: 8px 12px;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.2s;
  font-size: 14px;
  color: var(--text-primary);
}

.suggestion-btn:hover {
  background-color: var(--hover-color);
}

.message {
  max-width: 800px;
  margin: 0 auto 24px;
  padding: 16px;
  border-radius: 12px;
  position: relative;
}

.message.user {
  background-color: var(--surface-variant-color);
  margin-left: 48px;
}

.message.assistant {
  background-color: var(--surface-color);
  margin-right: 48px;
}

.message.streaming {
  opacity: 0.9;
}

.message-header {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 8px;
}

.avatar.user {
  background-color: var(--primary);
  color: var(--on-primary);
}

.avatar.assistant {
  background-color: var(--secondary);
  color: var(--on-secondary);
}

.message-role {
  font-weight: 500;
  font-size: 14px;
}

.message-content {
  font-size: 15px;
  line-height: 1.5;
  white-space: pre-wrap;
}

/* 应用全局样式 */
.message-content :deep(pre) {
  background-color: var(--code-background);
  border-radius: 6px;
  padding: 12px;
  overflow-x: auto;
  margin: 16px 0;
}

.message-content :deep(code) {
  font-family: monospace;
  font-size: 14px;
}

.message-content :deep(p) {
  margin: 8px 0;
}

.message-content :deep(ul), .message-content :deep(ol) {
  padding-left: 24px;
  margin: 8px 0;
}

.message-content :deep(h1), .message-content :deep(h2), .message-content :deep(h3),
.message-content :deep(h4), .message-content :deep(h5) {
  margin-top: 16px;
  margin-bottom: 8px;
}

.message-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 16px 0;
}

.message-content :deep(th), .message-content :deep(td) {
  border: 1px solid var(--divider-color);
  padding: 8px;
  text-align: left;
}

.message-content :deep(a) {
  color: var(--primary);
  text-decoration: none;
}

.message-content :deep(a:hover) {
  text-decoration: underline;
}

.message-actions {
  position: absolute;
  top: 8px;
  right: 8px;
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.message:hover .message-actions {
  opacity: 1;
}

.action-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 4px;
  border-radius: 4px;
}

.action-btn:hover {
  background-color: var(--hover-color);
}

.streaming-indicator {
  display: flex;
  gap: 4px;
  margin-top: 12px;
  justify-content: center;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--text-secondary);
  animation: pulse 1.5s infinite ease-in-out;
}

.dot:nth-child(2) {
  animation-delay: 0.2s;
}

.dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes pulse {
  0%, 100% {
    opacity: 0.3;
    transform: scale(0.8);
  }
  50% {
    opacity: 1;
    transform: scale(1.2);
  }
}

.input-container {
  padding: 16px;
  background-color: var(--surface-color);
  border-top: 1px solid var(--divider-color);
}

.input-wrapper {
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  align-items: flex-end;
  background-color: var(--background-color);
  border: 1px solid var(--divider-color);
  border-radius: 12px;
  padding: 8px 12px;
}

textarea {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  font-size: 15px;
  font-family: inherit;
  padding: 4px 0;
  max-height: 200px;
  color: var(--text-primary);
}

.send-btn {
  background-color: var(--primary);
  color: var(--on-primary);
  border: none;
  border-radius: 50%;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  margin-left: 8px;
  transition: background-color 0.2s;
}

.send-btn:hover {
  background-color: var(--primary-dark);
}

.send-btn:disabled {
  background-color: var(--text-disabled);
  cursor: not-allowed;
}

.input-help {
  max-width: 800px;
  margin: 8px auto 0;
  text-align: right;
  font-size: 12px;
  color: var(--text-secondary);
}

kbd {
  background-color: var(--surface-variant-color);
  border: 1px solid var(--divider-color);
  border-radius: 3px;
  font-size: 11px;
  padding: 2px 5px;
}

.error-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px;
  text-align: center;
}

.error-icon, .warning-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.error-icon {
  color: #F44336;
}

.warning-icon {
  color: #FF9800;
}

/* 响应式调整 */
@media (max-width: 768px) {
  .chat-header {
    padding: 8px 12px;
  }
  
  .chat-title h1 {
    font-size: 16px;
  }
  
  .messages-container {
    padding: 12px;
  }
  
  .message {
    padding: 12px;
  }
  
  .message.user {
    margin-left: 32px;
  }
  
  .message.assistant {
    margin-right: 32px;
  }
  
  .welcome-message {
    padding: 16px;
  }
  
  .suggestion-buttons {
    grid-template-columns: 1fr;
  }
  
  .input-container {
    padding: 12px;
  }
}
</style> 