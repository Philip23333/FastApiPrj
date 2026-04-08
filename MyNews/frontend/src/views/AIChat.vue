<script setup>
import { ref } from 'vue'
import axios from 'axios'
import { withApiBase } from '../config/api'

const message = ref('')
const systemPrompt = ref('你是新闻助手，请用简洁中文回答。')
const temperature = ref(0.3)
const loading = ref(false)
const errorMessage = ref('')
const messages = ref([])

const pushUserMessage = (content) => {
  messages.value.push({ role: 'user', content, timestamp: new Date().toLocaleTimeString() })
}

const pushAssistantMessage = (content, model = '') => {
  messages.value.push({
    role: 'assistant',
    content,
    model,
    timestamp: new Date().toLocaleTimeString(),
  })
}

const sendMessage = async () => {
  const content = message.value.trim()
  if (!content || loading.value) {
    return
  }

  errorMessage.value = ''
  pushUserMessage(content)
  loading.value = true

  try {
    const response = await axios.post(withApiBase('/ai/chat'), {
      message: content,
      system_prompt: systemPrompt.value.trim() || null,
      temperature: Number(temperature.value),
    })

    const payload = response?.data?.data
    const answer = payload?.answer || 'AI 未返回内容'
    const model = payload?.model || ''
    pushAssistantMessage(answer, model)
    message.value = ''
  } catch (error) {
    errorMessage.value = error?.response?.data?.message || error?.response?.data?.detail || '请求失败，请检查后端与 AI 配置'
  } finally {
    loading.value = false
  }
}

const clearMessages = () => {
  messages.value = []
  errorMessage.value = ''
}
</script>

<template>
  <div class="ai-chat-page">
    <div class="header">
      <h1>AI 对话测试页</h1>
      <p>用于单独联调后端 /ai/chat 接口。请先登录再测试。</p>
    </div>

    <div class="panel config-panel">
      <label>
        系统提示词
        <textarea v-model="systemPrompt" rows="3" placeholder="可选，控制 AI 回答风格" />
      </label>

      <label>
        temperature: {{ temperature }}
        <input v-model.number="temperature" type="range" min="0" max="1" step="0.1" />
      </label>
    </div>

    <div class="panel chat-panel">
      <div class="chat-toolbar">
        <strong>会话记录</strong>
        <button type="button" class="clear-btn" @click="clearMessages">清空</button>
      </div>

      <div v-if="!messages.length" class="empty-state">暂无消息，发送第一条内容开始测试。</div>

      <div v-else class="message-list">
        <div
          v-for="(item, index) in messages"
          :key="`${item.role}-${index}`"
          class="message-item"
          :class="item.role"
        >
          <div class="meta">
            <span>{{ item.role === 'user' ? '你' : 'AI' }}</span>
            <span>{{ item.timestamp }}</span>
            <span v-if="item.model" class="model">{{ item.model }}</span>
          </div>
          <div class="content">{{ item.content }}</div>
        </div>
      </div>

      <div v-if="errorMessage" class="error">{{ errorMessage }}</div>

      <div class="composer">
        <textarea
          v-model="message"
          rows="4"
          placeholder="请输入问题，例如：总结今天科技新闻热点"
          @keydown.ctrl.enter.prevent="sendMessage"
        />
        <button type="button" :disabled="loading" @click="sendMessage">
          {{ loading ? '发送中...' : '发送（Ctrl+Enter）' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ai-chat-page {
  max-width: 980px;
  margin: 0 auto;
  padding: 24px 16px 40px;
  color: #1f2937;
}

.header h1 {
  margin: 0;
  font-size: 28px;
}

.header p {
  margin: 8px 0 18px;
  color: #6b7280;
}

.panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 14px;
  margin-bottom: 14px;
}

.config-panel label {
  display: block;
  font-size: 14px;
  color: #374151;
  margin-bottom: 12px;
}

textarea {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  resize: vertical;
  padding: 10px;
  font-size: 14px;
  margin-top: 6px;
}

input[type='range'] {
  width: 100%;
  margin-top: 8px;
}

.chat-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.clear-btn {
  border: 1px solid #d1d5db;
  background: #fff;
  color: #374151;
  border-radius: 8px;
  padding: 6px 10px;
  cursor: pointer;
}

.empty-state {
  border: 1px dashed #d1d5db;
  border-radius: 8px;
  padding: 14px;
  color: #6b7280;
}

.message-list {
  max-height: 420px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.message-item {
  border-radius: 10px;
  padding: 10px;
}

.message-item.user {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
}

.message-item.assistant {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
}

.meta {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 6px;
}

.model {
  color: #2563eb;
}

.content {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.5;
}

.error {
  color: #b91c1c;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  padding: 8px 10px;
  margin-bottom: 10px;
}

.composer button {
  margin-top: 10px;
  background: #111827;
  border: none;
  color: #fff;
  border-radius: 8px;
  padding: 10px 14px;
  cursor: pointer;
}

.composer button:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .ai-chat-page {
    padding: 16px 10px 24px;
  }

  .header h1 {
    font-size: 22px;
  }
}
</style>
