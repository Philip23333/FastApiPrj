<script setup>
import { computed, nextTick, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import AuthModal from '../components/AuthModal.vue'
import TopNavBar from '../components/TopNavBar.vue'
import { useTopNavAuth } from '../composables/useTopNavAuth'
import { API_BASE_URL, withApiBase } from '../config/api'

const API_BASE = API_BASE_URL

const router = useRouter()
const {
  currentUser,
  restoreCurrentUser,
  handleAuthSuccess,
  logout,
  goHome,
  goToProfile,
  handlePublishClick,
} = useTopNavAuth()

// 状态管理
const categories = ref([])

const activeCategoryId = ref(0) // 0 代表推荐/全部
const newsList = ref([])
const loading = ref(false)
const errorMsg = ref('')

const currentPage = ref(1)
const hasMore = ref(true)

const hotList = ref([])
const hotPage = ref(1)
const hotPageSize = 8
const HOT_MIN_VIEWS_THRESHOLD = 10000
const hotLoading = ref(false)
const hotErrorMsg = ref('')
const hotSpinning = ref(false)
const canRefreshHot = ref(true)
const hotRefreshCooldownMs = 1000
const hotRefreshMinSpinMs = 500

const showAIPanel = ref(false)
const qaQuestion = ref('')
const qaLoading = ref(false)
const qaError = ref('')
const qaMessages = ref([])
const qaListRef = ref(null)
const showCitationDetail = ref(false)
const activeCitation = ref(null)

const askerId = computed(() => {
  const nickname = (currentUser.value?.nickname || '').trim()
  if (nickname) return nickname
  const username = (currentUser.value?.username || '').trim()
  if (username) return username
  return '访客'
})

// 统一提取接口错误信息。
const getApiErrorMessage = (error, fallback) => {
  return error?.response?.data?.message || error?.response?.data?.detail || fallback
}

// 从 SSE 缓冲区中切出一个完整事件块（兼容 LF/CRLF）。
const splitSseEventBlock = (bufferRef) => {
  const lfBoundary = bufferRef.value.indexOf('\n\n')
  const crlfBoundary = bufferRef.value.indexOf('\r\n\r\n')

  if (lfBoundary < 0 && crlfBoundary < 0) return null
  if (lfBoundary >= 0 && (crlfBoundary < 0 || lfBoundary < crlfBoundary)) {
    const block = bufferRef.value.slice(0, lfBoundary)
    bufferRef.value = bufferRef.value.slice(lfBoundary + 2)
    return block
  }
  const block = bufferRef.value.slice(0, crlfBoundary)
  bufferRef.value = bufferRef.value.slice(crlfBoundary + 4)
  return block
}

// 解析单个 SSE 事件块，提取 event 名和 data 文本。
const parseSseEvent = (block) => {
  let eventName = 'message'
  let dataText = ''
  const lines = block.split('\n')
  for (const line of lines) {
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim()
      continue
    }
    if (line.startsWith('data:')) {
      dataText += line.slice(5).trimStart()
    }
  }
  return {
    eventName,
    payload: dataText ? JSON.parse(dataText) : {},
  }
}

const renderMarkdown = (content) => {
  const parsed = marked.parse(content || '', {
    gfm: true,
    breaks: true,
  })
  const html = typeof parsed === 'string' ? parsed : ''
  return DOMPurify.sanitize(html)
}

const shortTitle = (title) => {
  const value = String(title || '').trim()
  if (!value) return '未命名来源'
  return value.length > 10 ? `${value.slice(0, 10)}...` : value
}

const formatSimilarity = (score) => {
  const value = Number(score || 0)
  if (!Number.isFinite(value)) return '0.00'
  return value.toFixed(3)
}

const openCitationDetail = (citation) => {
  activeCitation.value = citation
  showCitationDetail.value = true
}

const closeCitationDetail = () => {
  showCitationDetail.value = false
  activeCitation.value = null
}

const openAIPanel = () => {
  // 打开 AI 面板时立即恢复历史问答。
  if (!currentUser.value?.id) {
    showAuthModal.value = true
    return
  }
  showAIPanel.value = true
  loadQaHistory()
}

const closeAIPanel = () => {
  showAIPanel.value = false
}

const scrollQaToBottom = async () => {
  await nextTick()
  const el = qaListRef.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

const askRagQuestion = async () => {
  // SSE 问答主流程：先插入占位消息，再按 delta 增量渲染。
  const question = qaQuestion.value.trim()
  if (!question || qaLoading.value) return

  qaError.value = ''
  qaMessages.value.push({
    role: 'user',
    content: question,
    askerId: askerId.value,
    time: new Date().toLocaleTimeString(),
  })
  qaQuestion.value = ''
  await scrollQaToBottom()

  qaLoading.value = true
  qaMessages.value.push({
    role: 'assistant',
    content: '',
    citations: [],
    model: '',
    time: new Date().toLocaleTimeString(),
    streaming: true,
    typingStatus: '正在连接问答服务...',
  })
  const assistantIndex = qaMessages.value.length - 1
  await scrollQaToBottom()

  try {
    const token = localStorage.getItem('accessToken')
    const response = await fetch(withApiBase('/ai/qa/stream'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        question,
        top_k: 4,
      }),
    })

    if (!response.ok) {
      let message = `AI问答失败(${response.status})`
      try {
        const body = await response.json()
        message = body?.message || body?.detail || message
      } catch (_) {
        // ignore non-json error response
      }
      throw new Error(message)
    }

    if (!response.body) {
      throw new Error('流式响应不可用，请检查后端配置')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    const bufferRef = { value: '' }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      bufferRef.value += decoder.decode(value, { stream: true })

      while (true) {
        const block = splitSseEventBlock(bufferRef)
        if (block == null) break
        if (!block.trim()) continue

        const { eventName, payload } = parseSseEvent(block)
        const assistantMsg = qaMessages.value[assistantIndex]
        if (!assistantMsg) continue

        if (eventName === 'status') {
          assistantMsg.typingStatus = payload?.message || ''
        } else if (eventName === 'citations') {
          assistantMsg.citations = Array.isArray(payload?.citations) ? payload.citations : []
        } else if (eventName === 'delta') {
          assistantMsg.content += payload?.content || ''
          await scrollQaToBottom()
        } else if (eventName === 'done') {
          assistantMsg.model = payload?.model || ''
          assistantMsg.citations = Array.isArray(payload?.citations) ? payload.citations : []
          assistantMsg.streaming = false
          assistantMsg.typingStatus = ''
          await scrollQaToBottom()
        } else if (eventName === 'error') {
          throw new Error(payload?.message || 'AI问答失败，请稍后重试')
        }
      }
    }

    const assistantMsg = qaMessages.value[assistantIndex]
    if (assistantMsg) {
      assistantMsg.streaming = false
      assistantMsg.typingStatus = ''
      if (!assistantMsg.content.trim()) {
        assistantMsg.content = '暂时没有生成回答。'
      }
    }
  } catch (err) {
    const assistantMsg = qaMessages.value[assistantIndex]
    if (assistantMsg) {
      assistantMsg.streaming = false
      assistantMsg.typingStatus = ''
    }
    qaError.value = err?.message || getApiErrorMessage(err, 'AI问答失败，请稍后重试')
  } finally {
    qaLoading.value = false
  }
}

const formatChatTime = (value) => {
  if (!value) return new Date().toLocaleTimeString()
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return new Date().toLocaleTimeString()
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const loadQaHistory = async () => {
  // 每次打开面板时拉取最近历史，按“问->答”顺序重建会话。
  if (!currentUser.value?.id) return
  try {
    const response = await axios.get(withApiBase('/ai/qa/history'), {
      params: { page: 1, size: 20 },
    })
    const items = response?.data?.data?.items
    if (!Array.isArray(items)) return

    const messages = []
    const ordered = [...items].reverse()
    for (const item of ordered) {
      const question = String(item?.question || '').trim()
      const answer = String(item?.answer || '').trim()
      if (!question || !answer) continue

      messages.push({
        role: 'user',
        content: question,
        askerId: askerId.value,
        time: formatChatTime(item?.created_at),
      })
      messages.push({
        role: 'assistant',
        content: answer,
        citations: Array.isArray(item?.citations) ? item.citations : [],
        model: item?.model || '',
        time: formatChatTime(item?.created_at),
        streaming: false,
        typingStatus: '',
      })
    }
    qaMessages.value = messages
    await scrollQaToBottom()
  } catch (err) {
    qaError.value = getApiErrorMessage(err, '加载问答历史失败')
  }
}

// 获取分类标签
const fetchCategories = async () => {
  try {
    const response = await axios.get(withApiBase('/news/categories'))
    if (response.data && response.data.code === 200) {
      categories.value = response.data.data
    }
  } catch (err) {
    console.error('分类获取失败:', err)
  }
}

// 获取新闻流（今日头条是无限滚动/点加载更多模式）
// append 参数决定是直接覆盖还是追加数据
const fetchNews = async (page = 1, append = false) => {
  // 信息流分页加载：append 为 true 时执行“加载更多”追加模式。
  if (loading.value) return
  loading.value = true
  errorMsg.value = ''
  
  try {
    let url = withApiBase(`/news/?page=${page}&size=10`)
    if (activeCategoryId.value !== 0) {
      url = withApiBase(`/news/categories/${activeCategoryId.value}/news?page=${page}&size=10`)
    }
    const response = await axios.get(url)
    if (response.data && response.data.code === 200) {
      const newItems = response.data.data.items
      
      if (append) {
        newsList.value = [...newsList.value, ...newItems]
      } else {
        newsList.value = newItems
      }
      
      currentPage.value = response.data.data.page
      hasMore.value = currentPage.value < response.data.data.totalPages
    } else {
      errorMsg.value = '服务器返回数据格式不正确'
    }
  } catch (err) {
    console.error(err)
    errorMsg.value = '请求接口失败，请检查 FastAPI 服务状态'
  } finally {
    loading.value = false
  }
}

// 切换头部的频道
const selectCategory = (id) => {
  if (activeCategoryId.value === id) return
  activeCategoryId.value = id
  newsList.value = [] // 切换时先清空视觉
  fetchNews(1, false)
}

// 加载更多文章
const loadMore = () => {
  if (hasMore.value) {
    fetchNews(currentPage.value + 1, true)
  }
}

const fetchHotList = async (page = 1) => {
  // 热榜分页加载；触底后由调用方决定是否回到第一页。
  if (hotLoading.value) return false

  hotLoading.value = true
  hotErrorMsg.value = ''

  try {
    const response = await axios.get(withApiBase('/news/hot'), {
      params: {
        min_views: HOT_MIN_VIEWS_THRESHOLD,
        page,
        size: hotPageSize,
      }
    })

    if (response.data?.code === 200) {
      hotList.value = response.data.data || []
      hotPage.value = page
      return true
    }

    if (response.data?.message === 'reached_end') {
      return false
    }

    hotErrorMsg.value = '热榜数据返回异常'
    return false
  } catch (err) {
    console.error('热榜获取失败:', err)
    hotErrorMsg.value = '热榜加载失败，请稍后重试'
    return false
  } finally {
    hotLoading.value = false
  }
}

// 点击“换一换”时切到下一批；若触底则从第一批重新开始
const refreshHotList = async () => {
  if (hotLoading.value || !canRefreshHot.value) return

  const start = Date.now()
  canRefreshHot.value = false
  hotSpinning.value = true

  const nextPage = hotPage.value + 1
  const hasNextBatch = await fetchHotList(nextPage)
  if (!hasNextBatch) {
    await fetchHotList(1)
  }

  const elapsed = Date.now() - start
  const remainSpin = Math.max(0, hotRefreshMinSpinMs - elapsed)

  setTimeout(() => {
    hotSpinning.value = false
  }, remainSpin)

  setTimeout(() => {
    canRefreshHot.value = true
  }, Math.max(hotRefreshCooldownMs, remainSpin))
}

// 时间人性化转换（仿头条格式：刚发布显示分钟前/小时前，较早显示月日）
const formatTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = Math.floor((now - date) / 1000) // 差值秒数

  if (diff < 3600) {
    return Math.max(1, Math.floor(diff / 60)) + '分钟前'
  } else if (diff < 86400) {
    return Math.floor(diff / 3600) + '小时前'
  } else {
    // 跨天则显示 03-24 格式
    return `${(date.getMonth() + 1).toString().padStart(2,'0')}-${date.getDate().toString().padStart(2,'0')}`
  }
}

const normalizeImageUrl = (url) => {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  if (url.startsWith('/')) return `${API_BASE}${url}`
  return `${API_BASE}/${url}`
}

const goToDetail = (id) => {
  if (!currentUser.value?.id) {
    window.dispatchEvent(new CustomEvent('auth-required', {
      detail: {
        message: '请先登录后查看新闻详情。',
        reason: 'detail-access',
        targetPath: `/news/${id}`,
        fallbackPath: '/',
      }
    }))
    return
  }
  router.push(`/news/${id}`)
}

onMounted(() => {
  fetchCategories()
  fetchNews(1)
  fetchHotList(1)
  restoreCurrentUser()
})

// --- 登录/注册相关状态与逻辑 ---
const showAuthModal = ref(false)
const handlePublishClickFromNav = () => {
  handlePublishClick({ openLoginModal: () => { showAuthModal.value = true } })
}
</script>

<template>
  <div class="toutiao-layout">
    <TopNavBar
      :current-user="currentUser"
      @logo-click="goHome"
      @login-click="showAuthModal = true"
      @profile-click="goToProfile"
      @logout-click="logout"
      @publish-click="handlePublishClickFromNav"
    />

    <!-- 底部主体内容区 (上边距为了躲避固定header) -->
    <main class="tt-main">
      
      <!-- 左侧分类频道栏 -->
      <aside class="tt-sidebar-left">
        <ul class="channel-list">
          <li :class="{ active: activeCategoryId === 0 }" @click="selectCategory(0)">
            推荐
          </li>
          <li 
            v-for="cat in categories" 
            :key="cat.id" 
            :class="{ active: activeCategoryId === cat.id }" 
            @click="selectCategory(cat.id)">
            {{ cat.name }}
          </li>
        </ul>
      </aside>

      <!-- 中间主新闻信息流 (Feed) -->
      <div class="tt-feed">
        <div v-if="errorMsg" class="error-tip">{{ errorMsg }}</div>
        
        <div class="news-list" v-if="newsList.length > 0">
          <div class="news-card" v-for="(news, index) in newsList" :key="index" @click="goToDetail(news.id)">
            <div class="news-content">
              <h3 class="news-title">{{ news.title }}</h3>
              <p class="news-desc">{{ news.description }}</p>
              
              <!-- 底部元数据区 -->
              <div class="news-meta">
                <span class="meta-tag" v-if="news.category_name" :class="{ 'red-tag': index < 2 }">
                  {{ news.category_name || '热点' }}
                </span>
                <span class="meta-author">{{ news.author || '新华社' }} ·</span>
                <span class="meta-views">{{ news.views }} 浏览 ·</span>
                <span class="meta-time">{{ formatTime(news.publish_time) }}</span>
              </div>
            </div>
            
            <!-- 右侧新闻图片 -->
            <img v-if="news.image" :src="normalizeImageUrl(news.image)" alt="news cover" class="news-img" />
          </div>
        </div>

        <div v-if="!loading && !errorMsg && newsList.length === 0" class="empty-tip">
          该分类下暂时没有新闻数据～
        </div>

        <!-- 加载更多区域 -->
        <div class="load-more-wrap" v-if="newsList.length > 0">
          <button class="load-more-btn" @click="loadMore" :disabled="loading || !hasMore">
            <span v-if="loading">加载中，请稍候...</span>
            <span v-else-if="hasMore">点击加载更多</span>
            <span v-else class="no-more">没有更多头条了</span>
          </button>
        </div>
      </div>

      <!-- 右侧热点资讯悬浮榜单 -->
      <aside class="tt-sidebar-right">
        <div class="hot-board">
          <div class="board-header">
            <h3>头条热榜</h3>
            <span
              class="refresh"
              :class="{ 'is-disabled': hotLoading || !canRefreshHot }"
              @click="refreshHotList"
            >
              <span class="refresh-icon" :class="{ spinning: hotSpinning }">↻</span>
              {{ hotLoading ? '加载中...' : '换一换' }}
            </span>
          </div>
          <div v-if="hotErrorMsg" class="hot-error">{{ hotErrorMsg }}</div>
          <ul class="hot-list">
            <li v-for="(hot, index) in hotList" :key="'hot-'+hot.id" @click="goToDetail(hot.id)">
              <span class="rank" :class="'rank-'+(index+1)">{{ index + 1 }}</span>
              <p class="hot-title">{{ hot.title }}</p>
              <span class="hot-views">{{ hot.views }} 浏览</span>
              <span v-if="index===0" class="hot-badge red">爆</span>
              <span v-else-if="index<3" class="hot-badge orange">热</span>
            </li>
          </ul>
          <div v-if="!hotLoading && hotList.length === 0 && !hotErrorMsg" class="hot-empty">
            暂无热榜数据
          </div>
        </div>
      </aside>

    </main>
    
    <AuthModal
      v-model:visible="showAuthModal"
      @success="handleAuthSuccess"
    />

    <button v-if="!showAIPanel" class="ai-float-btn" type="button" @click="openAIPanel" title="AI问答助手">
      <span class="ai-float-icon">AI</span>
    </button>

    <section v-if="showAIPanel" class="ai-chat-window">
      <div class="ai-panel">
        <header class="ai-panel-head">
          <div>
            <h3>AI问答助手</h3>
            <p>回答基于向量库检索结果，并附带来源</p>
          </div>
          <button type="button" class="ai-close" aria-label="收起聊天窗口" @click="closeAIPanel">×</button>
        </header>

        <div ref="qaListRef" class="ai-chat-list">
          <div v-if="qaMessages.length === 0" class="ai-empty">输入问题开始提问，例如：今天体育热点有哪些？</div>
          <article
            v-for="(msg, idx) in qaMessages"
            :key="`qa-${idx}`"
            class="ai-msg"
            :class="msg.role"
          >
            <div class="ai-msg-meta">
              <span>{{ msg.role === 'user' ? msg.askerId || askerId : 'AI助手' }}</span>
              <span>{{ msg.time }}</span>
              <span v-if="msg.model" class="ai-model">{{ msg.model }}</span>
            </div>
            <div
              v-if="msg.role === 'assistant'"
              class="ai-msg-content markdown-content"
              v-html="renderMarkdown(msg.content)"
            ></div>
            <div v-else class="ai-msg-content">{{ msg.content }}</div>
            <div v-if="msg.role === 'assistant' && msg.typingStatus" class="ai-stream-status">{{ msg.typingStatus }}</div>
            <span v-if="msg.role === 'assistant' && msg.streaming" class="typing-cursor">▍</span>

            <div v-if="msg.role === 'assistant' && msg.citations?.length" class="citation-links">
              <button
                v-for="(cite, cIdx) in msg.citations"
                :key="`cite-${idx}-${cIdx}`"
                type="button"
                class="citation-link"
                @click="openCitationDetail(cite)"
              >
                {{ shortTitle(cite.title) }} · {{ formatSimilarity(cite.score) }}
              </button>
            </div>
          </article>
        </div>

        <p v-if="qaError" class="ai-error">{{ qaError }}</p>

        <footer class="ai-composer">
          <textarea
            v-model="qaQuestion"
            rows="3"
            placeholder="请输入你的问题，Ctrl+Enter发送"
            @keydown.ctrl.enter.prevent="askRagQuestion"
          ></textarea>
          <button type="button" :disabled="qaLoading" @click="askRagQuestion">
            {{ qaLoading ? '思考中...' : '发送问题' }}
          </button>
        </footer>
      </div>
    </section>

    <div v-if="showCitationDetail" class="citation-detail-overlay" @click.self="closeCitationDetail">
      <div class="citation-detail-card">
        <div class="citation-detail-head">
          <h4>来源详情</h4>
          <button type="button" @click="closeCitationDetail" class="ai-close" >×</button>
        </div>
        <p class="citation-detail-title">{{ activeCitation?.title || '未命名新闻' }}</p>
        <p class="citation-detail-score">相似度：{{ formatSimilarity(activeCitation?.score) }}</p>
        <div class="citation-detail-snippet">{{ activeCitation?.snippet || '无摘要片段' }}</div>
      </div>
    </div>
  </div>
</template>

<style>
/* 全局充当 Base CSS，因为 App.vue 是根组件 */
body {
  background-color: #f4f5f6; /* 头条标志性灰白背景 */
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  color: #222;
}
* {
  box-sizing: border-box;
}
</style>

<style scoped>
/* 最外层包裹 */
.toutiao-layout {
  min-height: 100vh;
}

/* ================= 页面主体三列 ================= */
.tt-main {
  width: 1170px;
  margin: 76px auto 0; /* 留出 header 位置 + 上边距 */
  display: flex;
  align-items: flex-start;
  gap: 20px;
}

/* 1. 左侧频道菜单 (150px) */
.tt-sidebar-left {
  width: 150px;
  flex-shrink: 0;
  position: sticky;
  top: 76px; /* 滑动时固定 */
  background: white;
  border-radius: 8px;
  padding: 8px 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}
.channel-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.channel-list li {
  padding: 12px 0;
  text-align: center;
  font-size: 16px;
  color: #444;
  cursor: pointer;
  transition: all 0.2s;
  margin: 4px 8px;
  border-radius: 6px;
}
.channel-list li:hover {
  background-color: #f4f5f6;
  color: #f04142;
}
.channel-list li.active {
  background-color: #f04142;
  color: #fff;
  font-weight: bold;
}

/* 2. 中间信息流 (660px 核心宽) */
.tt-feed {
  flex-grow: 1;
  max-width: 660px;
  background: white;
  border-radius: 8px;
  min-height: 800px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}
/* 单个新闻文章卡片 */
.news-card {
  display: flex;
  align-items: stretch;
  gap: 16px;
  padding: 16px 20px;
  border-bottom: 1px solid #e8e8e8;
  cursor: pointer;
  transition: background-color 0.2s;
}
.news-card:hover {
  background-color: #fafafa;
}
.news-img {
  width: 160px;
  height: 104px;
  object-fit: cover;
  border-radius: 4px;
  flex-shrink: 0;
}
.news-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.news-title {
  font-size: 20px;
  color: #222;
  font-weight: 700;
  line-height: 1.5;
  margin: 0 0 8px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  word-break: break-word;
  text-align: left;
}
.news-desc {
  font-size: 14px;
  color: #555;
  margin: 0 0 12px 0;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2; /* 限制2行 */
  line-clamp: 2;
  overflow: hidden;
  text-overflow: ellipsis;
  text-align: left;
}
/* 元数据信息区（类似 科技 · 新华社 · 200评论 · 2小时前） */
.news-meta {
  font-size: 13px;
  color: #777;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-start; /* 元数据向左对齐更符合头条习惯 */
  gap: 8px;
}
.meta-tag {
  color: #f04142;
  background-color: rgba(240, 65, 66, 0.08); /* 浅一点的红 */
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 500;
}
/* 有些置顶用红色，正常的也可以不用背景色，这里为了好看统一做一点色 */
.meta-tag:not(.red-tag) {
  color: #406599;
  background-color: rgba(64, 101, 153, 0.08);
}

/* 加载更多按钮 */
.load-more-wrap {
  padding: 20px;
  text-align: center;
}
.load-more-btn {
  background-color: #f8f9fa;
  border: 1px solid #e8e8e8;
  color: #406599;
  font-size: 15px;
  padding: 10px 30px;
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.2s;
  width: 100%; /* 占满宽度 */
}
.load-more-btn:hover:not(:disabled) {
  background-color: #f0f1f2;
}
.load-more-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
  color: #999;
}
.empty-tip {
  padding: 50px 0;
  text-align: center;
  color: #999;
}

/* 3. 右侧榜单区 (约 300px) */
.tt-sidebar-right {
  width: 320px;
  flex-shrink: 0;
}
.hot-board {
  background: white;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.02);
  position: sticky;
  top: 76px;
}
.board-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #f0f0f0;
  padding-bottom: 12px;
  margin-bottom: 12px;
}
.board-header h3 {
  margin: 0;
  font-size: 18px;
  color: #222;
}
.board-header .refresh {
  font-size: 13px;
  color: #406599;
  cursor: pointer;
  user-select: none;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.board-header .refresh:hover {
  text-decoration: underline;
}
.board-header .refresh.is-disabled {
  color: #98a3b3;
  cursor: not-allowed;
  text-decoration: none;
}
.refresh-icon {
  display: inline-block;
  transform-origin: center;
}
.refresh-icon.spinning {
  animation: hot-refresh-spin 0.6s linear infinite;
}
@keyframes hot-refresh-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.hot-error {
  font-size: 12px;
  color: #f04142;
  margin-bottom: 8px;
}
/* 列表 */
.hot-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.hot-list li {
  display: flex;
  align-items: flex-start;
  min-width: 0;
  margin-bottom: 16px;
  cursor: pointer;
  text-align: left;
}
.hot-list li:last-child {
  margin-bottom: 0;
}
.rank {
  font-size: 16px;
  font-weight: bold;
  font-style: italic;
  color: #999;
  width: 24px;
  margin-top: 2px;
}
/* 前三名变色 */
.rank-1, .rank-2, .rank-3 {
  color: #f04142;
}
.hot-title {
  margin: 0;
  flex: 1;
  min-width: 0;
  font-size: 15px;
  color: #222;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hot-title:hover {
  color: #406599;
}
.hot-views {
  font-size: 12px;
  color: #999;
  margin-left: 8px;
  margin-top: 2px;
  white-space: nowrap;
}
/* 小标签 */
.hot-badge {
  font-size: 10px;
  color: white;
  padding: 1px 4px;
  border-radius: 4px;
  margin-left: 8px;
  margin-top: 2px;
}
.hot-badge.red { background-color: #f04142; }
.hot-badge.orange { background-color: #ff7e00; }
.hot-empty {
  font-size: 13px;
  color: #999;
  text-align: center;
  padding: 8px 0 4px;
}

.ai-float-btn {
  position: fixed;
  right: 24px;
  top: 96px;
  width: 62px;
  height: 62px;
  border: none;
  border-radius: 50%;
  background: linear-gradient(135deg, #0ea5e9, #2563eb);
  color: #fff;
  cursor: pointer;
  box-shadow: 0 12px 28px rgba(14, 116, 230, 0.35);
  z-index: 1250;
}

.ai-float-icon {
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 0.5px;
}

.ai-chat-window {
  position: fixed;
  right: 0;
  top: 76px;
  bottom: 0;
  width: min(620px, 48vw);
  z-index: 1240;
}

.ai-panel {
  width: 100%;
  height: 100%;
  background: #fff;
  color: #111827;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.2);
  border-radius: 0;
  overflow: hidden;
  text-align: left;
  border-radius: 10px;
}

.ai-panel-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  padding: 16px;
  border-bottom: 1px solid #e5e7eb;
}

.ai-panel-head h3 {
  margin: 0;
  font-size: 20px;
}

.ai-panel-head p {
  margin: 6px 0 0;
  font-size: 12px;
  color: #64748b;
}

.ai-close {
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #111827;
  border-radius: 8px;
  height: 34px;
  width: 34px;
  font-size: 22px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  cursor: pointer;
}

.ai-chat-list {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
  background: linear-gradient(180deg, #f8fbff 0%, #f9fafb 100%);
  text-align: left;
}

.ai-empty {
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  padding: 12px;
  color: #64748b;
  background: #fff;
}

.ai-msg {
  border-radius: 10px;
  padding: 10px;
  margin-bottom: 10px;
  font-size: 14px;
}

.ai-msg.user {
  background: #e6f3ff;
  border: 1px solid #bfdbfe;
}

.ai-msg.assistant {
  background: #fff;
  border: 1px solid #e5e7eb;
}

.ai-msg-meta {
  display: flex;
  gap: 8px;
  color: #64748b;
  font-size: 12px;
  margin-bottom: 6px;
}

.ai-model {
  color: #2563eb;
}

.ai-msg-content {
  white-space: pre-wrap;
  line-height: 1.55;
  color: #1e293b;
}

.ai-stream-status {
  margin-top: 8px;
  font-size: 12px;
  color: #64748b;
}

.typing-cursor {
  display: inline-block;
  margin-top: 4px;
  color: #2563eb;
  animation: ai-cursor-blink 1s steps(2, start) infinite;
}

@keyframes ai-cursor-blink {
  to {
    visibility: hidden;
  }
}

.markdown-content :deep(*) {
  text-align: left;
}

.markdown-content :deep(p) {
  margin: 0 0 8px;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  padding-left: 20px;
  margin: 0 0 8px;
}

.markdown-content :deep(pre) {
  background: #f1f5f9;
  border-radius: 8px;
  padding: 10px;
  overflow-x: auto;
}

.citation-links {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.citation-link {
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 12px;
  cursor: pointer;
}

.citation-link:hover {
  border-color: #60a5fa;
  background: #dbeafe;
}

.citation-detail-overlay {
  position: fixed;
  inset: 0;
  z-index: 1300;
  background: rgba(15, 23, 42, 0.28);
  display: flex;
  align-items: center;
  justify-content: center;
}

.citation-detail-card {
  color: #000;
  width: min(560px, calc(100vw - 24px));
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 20px 40px rgba(15, 23, 42, 0.28);
  padding: 30px;
  text-align: left;
}

.citation-detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.citation-detail-head h4 {
  margin: 0;
}

.citation-detail-head button {
  border: 1px solid #cbd5e1;
  background: #fff;
  border-radius: 8px;
  height: 32px;
  padding: 0 10px;
  cursor: pointer;
}

.citation-detail-title {
  margin: 10px 0 6px;
  font-weight: 700;
  color: #0f172a;
}

.citation-detail-score {
  margin: 0 0 10px;
  color: #2563eb;
  font-size: 13px;
}

.citation-detail-snippet {
  white-space: pre-wrap;
  line-height: 1.65;
  color: #334155;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 10px;
}

.ai-error {
  margin: 0;
  padding: 10px 14px;
  color: #b91c1c;
  background: #fef2f2;
  border-top: 1px solid #fecaca;
}

.ai-composer {
  border-top: 1px solid #e5e7eb;
  padding: 12px;
  background: #fff;
}

.ai-composer textarea {
  width: 100%;
  border: 1px solid #cbd5e1;
  background: #f3f4f6;
  color: #111827;
  border-radius: 8px;
  resize: vertical;
  padding: 10px;
  font-size: 14px;
}

.ai-composer textarea::placeholder {
  color: #6b7280;
}

.ai-composer button {
  margin-top: 8px;
  border: none;
  background: #1d4ed8;
  color: #fff;
  border-radius: 8px;
  height: 36px;
  padding: 0 14px;
  cursor: pointer;
}

.ai-composer button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .ai-float-btn {
    width: 54px;
    height: 54px;
    right: 12px;
    top: 84px;
  }

  .ai-chat-window {
    left: 0;
    right: 0;
    top: 64px;
    bottom: 0;
    width: 100%;
  }
}

/* 登录相关样式 */
</style>
