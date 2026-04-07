<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import axios from 'axios'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import AuthModal from '../components/AuthModal.vue'
import TopNavBar from '../components/TopNavBar.vue'
import { useTopNavAuth } from '../composables/useTopNavAuth'
import { API_BASE_URL, withApiBase } from '../config/api'

const router = useRouter()
const route = useRoute()
const API_BASE = API_BASE_URL
const {
  currentUser,
  restoreCurrentUser,
  handleAuthSuccess,
  logout,
  goHome,
  goToProfile,
  handlePublishClick,
} = useTopNavAuth()

const newsId = ref(route.params.id)
const newsItem = ref(null)
const loading = ref(true)
const errorMsg = ref('')
const showAuthModal = ref(false)
const favoriteLoading = ref(false)
const isFavorited = ref(false)
const showSummaryDrawer = ref(false)
const summaryLoading = ref(false)
const summaryError = ref('')
const summaryInput = ref('提炼新闻要点，快速了解核心信息')
const summaryMessages = ref([])

// 相关推荐数据
const relatedNews = ref([])

const toAbsoluteUrl = (url) => {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  if (url.startsWith('/')) return `${API_BASE}${url}`
  return url
}

const renderedContentHtml = computed(() => {
  const raw = newsItem.value?.content || ''
  if (!raw) return ''

  const container = document.createElement('div')
  container.innerHTML = raw

  container.querySelectorAll('img').forEach((img) => {
    const src = img.getAttribute('src') || ''
    if (src) {
      img.setAttribute('src', toAbsoluteUrl(src))
    }
    img.setAttribute('loading', 'lazy')
  })

  container.querySelectorAll('a').forEach((a) => {
    a.setAttribute('target', '_blank')
    a.setAttribute('rel', 'noopener noreferrer nofollow')
  })

  return DOMPurify.sanitize(container.innerHTML)
})

const fetchRelatedNews = async (categoryId, currentNewsId) => {
  try {
    const response = await axios.get(withApiBase(`/news/categories/${categoryId}/news?page=1&size=20`))
    if (response.data && response.data.code === 200) {
      let items = response.data.data.items || []
      // 过滤当前展示的新闻
      items = items.filter(item => item.id != currentNewsId)
      // 随机打乱数组，取前 4 个
      items.sort(() => 0.5 - Math.random())
      relatedNews.value = items.slice(0, 4)
    }
  } catch (err) {
    console.error('获取相关推荐失败', err)
  }
}

const fetchNewsDetail = async () => {
  loading.value = true
  errorMsg.value = ''
  window.scrollTo(0, 0)
  try {
    const response = await axios.get(withApiBase(`/news/detail/${newsId.value}`))
    if (response.data && response.data.code === 200) {
      newsItem.value = response.data.data
      
      // 获取分类相关推荐
      if (newsItem.value.category_id) {
        fetchRelatedNews(newsItem.value.category_id, newsId.value)
      }
    } else {
      errorMsg.value = '文章未找到或已被删除'
    }
  } catch (err) {
    console.error(err)
    errorMsg.value = '获取文章详情失败'
  } finally {
    loading.value = false
  }
}

const reportViewHistory = async () => {
  if (!currentUser.value?.id || !newsId.value) return
  try {
    await axios.post(withApiBase(`/history/${newsId.value}`))
  } catch (err) {
    console.error('上报浏览记录失败', err)
  }
}

const fetchFavoriteStatus = async () => {
  if (!currentUser.value?.id || !newsId.value) {
    isFavorited.value = false
    return
  }

  try {
    const response = await axios.get(withApiBase(`/favorites/check/${newsId.value}`))
    if (response.data?.code === 200) {
      isFavorited.value = !!response.data.data
    }
  } catch (err) {
    console.error('获取收藏状态失败', err)
    isFavorited.value = false
  }
}

const toggleFavorite = async () => {
  if (favoriteLoading.value) return

  if (!currentUser.value?.id) {
    showAuthModal.value = true
    return
  }

  try {
    favoriteLoading.value = true
    if (isFavorited.value) {
      const res = await axios.delete(withApiBase(`/favorites/${newsId.value}`))
      if (res.data?.code === 200) {
        isFavorited.value = false
      }
      return
    }

    const res = await axios.post(withApiBase(`/favorites/${newsId.value}`))
    if (res.data?.code === 200) {
      isFavorited.value = true
    }
  } catch (err) {
    console.error('收藏操作失败', err)
    alert(err?.response?.data?.message || '收藏操作失败，请稍后重试')
  } finally {
    favoriteLoading.value = false
  }
}

const renderSummaryMarkdown = (content) => {
  const raw = content || ''
  const parsed = marked.parse(raw, { gfm: true, breaks: true })
  return DOMPurify.sanitize(typeof parsed === 'string' ? parsed : '')
}

const sendSummaryQuestion = async (question) => {
  const text = (question || summaryInput.value || '').trim()
  if (!text || summaryLoading.value) return

  summaryError.value = ''
  summaryMessages.value.push({
    role: 'user',
    content: text,
    time: new Date().toLocaleTimeString(),
  })

  summaryLoading.value = true
  try {
    const response = await axios.post(withApiBase(`/ai/news/${newsId.value}/chat`), {
      question: text,
      temperature: 0.2,
    })
    const data = response?.data?.data || {}
    summaryMessages.value.push({
      role: 'assistant',
      content: data.answer || 'AI未生成总结内容。',
      model: data.model || '',
      time: new Date().toLocaleTimeString(),
    })
  } catch (err) {
    summaryError.value = err?.response?.data?.message || err?.response?.data?.detail || 'AI总结失败，请稍后再试'
  } finally {
    summaryLoading.value = false
  }
}

const openSummaryDrawer = async () => {
  if (!currentUser.value?.id) {
    showAuthModal.value = true
    return
  }
  showSummaryDrawer.value = true

  if (summaryMessages.value.length === 0 && !summaryLoading.value) {
    await sendSummaryQuestion(summaryInput.value)
  }
}

const closeSummaryDrawer = () => {
  showSummaryDrawer.value = false
}

watch(() => route.params.id, (newId) => {
  if (newId) {
    newsId.value = newId
    fetchNewsDetail()
    fetchFavoriteStatus()
    reportViewHistory()
  }
})

const handlePublishClickFromNav = () => {
  handlePublishClick({ openLoginModal: () => { showAuthModal.value = true } })
}

const formatTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2,'0')}-${date.getDate().toString().padStart(2,'0')} ${date.getHours().toString().padStart(2,'0')}:${date.getMinutes().toString().padStart(2,'0')}`
}

onMounted(() => {
  restoreCurrentUser()
  fetchNewsDetail()
  fetchFavoriteStatus()
  reportViewHistory()
})

const handleAuthSuccessFromModal = async (payload) => {
  handleAuthSuccess(payload)
  await fetchFavoriteStatus()
  await reportViewHistory()
}
</script>

<template>
  <div class="toutiao-layout detail-layout">
    <TopNavBar
      :current-user="currentUser"
      @logo-click="goHome"
      @login-click="showAuthModal = true"
      @profile-click="goToProfile"
      @logout-click="logout"
      @publish-click="handlePublishClickFromNav"
    />

    <main class="tt-main detail-main">
      <div class="left-sidebar">
        <!-- 点赞、收藏、评论操作悬浮区 -->
        <div class="action-panel">
          <div class="action-btn">
            <span class="icon">💬</span>
            <span class="text">评论</span>
          </div>
          <div class="action-btn">
            <span class="icon">👍</span>
            <span class="text">点赞</span>
          </div>
          <div
            class="action-btn"
            :class="{ active: isFavorited }"
            @click="toggleFavorite"
          >
            <span class="icon">{{ isFavorited ? '★' : '☆' }}</span>
            <span class="text">{{ favoriteLoading ? '处理中' : (isFavorited ? '已收藏' : '收藏') }}</span>
          </div>
        </div>
      </div>

      <div class="article-container">
        <div v-if="loading" class="loading-tip">正在加载文章内容...</div>
        <div v-else-if="errorMsg" class="error-tip">{{ errorMsg }}</div>
        
        <article v-else class="article-body">
          <h1 class="article-title">{{ newsItem.title }}</h1>
          
          <div class="article-meta">
            <span class="author">{{ newsItem.author || '新华社' }}</span>
            <span class="time">{{ formatTime(newsItem.publish_time) }}</span>
            <span class="views">阅读 {{ newsItem.views }}</span>
          </div>

          <div class="split-line"></div>

          <!-- 新闻正文渲染 -->
          <div class="article-content">
             <img v-if="newsItem.image" :src="toAbsoluteUrl(newsItem.image)" class="article-cover" alt="封面配图"/>
             <div class="rich-content" v-html="renderedContentHtml"></div>
          </div>
          
          <!-- 相关推荐区域 -->
          <div class="related-recommendation">
            <div class="recommend-header">
              <h3>相关推荐</h3>
            </div>
            <div class="news-list">
              <div class="news-card" v-for="(news, index) in relatedNews" :key="index" @click="router.push(`/news/${news.id}`)">
                <div class="news-content">
                  <h3 class="news-title">{{ news.title }}</h3>
                  <p class="news-desc">{{ news.description }}</p>
                  
                  <div class="news-meta">
                    <span class="meta-author">{{ news.author }} ·</span>
                    <span class="meta-views">{{ news.views }} 阅读 ·</span>
                    <span class="meta-time">{{ formatTime(news.publish_time) }}</span>
                  </div>
                </div>
                
                <img v-if="news.image" :src="toAbsoluteUrl(news.image)" alt="news cover" class="news-img" />
              </div>
            </div>
          </div>
        </article>
      </div>

      <aside class="right-sidebar">

        <!-- 作者信息卡片 -->
        <div class="author-card" v-if="newsItem">
          <div class="author-info">
            <div class="avatar">真</div>
            <div class="name-box">
              <div class="name">{{ newsItem.author || '新华社' }}</div>
              <div class="desc">优质领域创作者</div>
            </div>
          </div>
          <button class="follow-btn">关注</button>
        </div>
      </aside>

      <button class="summary-float-trigger" type="button" @click="openSummaryDrawer">
        一键总结
      </button>
    </main>

    <section v-if="showSummaryDrawer" class="summary-chat-window">
      <section class="summary-drawer">
        <header>
          <div>
            <h3>AI总结对话</h3>
            <p>{{ newsItem?.title || '' }}</p>
          </div>
          <button type="button" class="summary-close" aria-label="收起总结对话" @click="closeSummaryDrawer">×</button>
        </header>

        <div class="summary-body">
          <article
            v-for="(msg, idx) in summaryMessages"
            :key="`sum-${idx}`"
            class="summary-chat-item"
            :class="msg.role"
          >
            <div class="summary-chat-meta">
              <span>{{ msg.role === 'user' ? (currentUser?.nickname || currentUser?.username || '你') : 'AI助手' }}</span>
              <span>{{ msg.time }}</span>
              <span v-if="msg.model" class="summary-chat-model">{{ msg.model }}</span>
            </div>
            <div v-if="msg.role === 'assistant'" class="summary-chat-content" v-html="renderSummaryMarkdown(msg.content)"></div>
            <div v-else class="summary-chat-content plain">{{ msg.content }}</div>
          </article>

          <div v-if="summaryLoading" class="summary-loading">正在生成总结...</div>
          <p v-if="summaryError" class="summary-error">{{ summaryError }}</p>

          <div class="summary-composer">
            <textarea
              v-model="summaryInput"
              rows="3"
              placeholder="提炼新闻要点，快速了解核心信息"
              @keydown.ctrl.enter.prevent="sendSummaryQuestion()"
            ></textarea>
            <button type="button" :disabled="summaryLoading" @click="sendSummaryQuestion()">
              {{ summaryLoading ? '生成中...' : '发送' }}
            </button>
          </div>
        </div>
      </section>
    </section>

    <AuthModal
      v-model:visible="showAuthModal"
      @success="handleAuthSuccessFromModal"
    />
  </div>
</template>

<style scoped>
.detail-layout {
  background-color: #fff;
}

/* 主体布局 */
.detail-main {
  width: 1170px;
  margin: 76px auto 0;
  display: flex;
  align-items: flex-start;
  gap: 20px;
  position: relative;
}

/* 1. 左操作面板 */
.left-sidebar {
  width: 150px;
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  padding-right: 20px;
}
.action-panel {
  position: sticky;
  top: 100px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.action-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 50px;
  height: 50px;
  background: #f4f5f6;
  border-radius: 50%;
  cursor: pointer;
  color: #555;
  transition: all 0.2s;
}
.action-btn:hover {
  background: #e8e8e8;
  color: #f04142;
}
.action-btn.active {
  background: #fdebec;
  color: #f04142;
}
.action-btn .icon {
  font-size: 20px;
}
.action-btn .text {
  font-size: 12px;
  margin-top: 2px;
}

/* 2. 文章主体 */
.article-container {
  flex-grow: 1;
  min-width: 0;
  max-width: 660px;
  padding: 0 10px;
}
.article-title {
  font-size: 32px;
  font-weight: 700;
  line-height: 1.4;
  color: #222;
  margin: 20px 0;
  text-align: left;
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.article-meta {
  display: flex;
  align-items: center;
  color: #777;
  font-size: 14px;
  gap: 16px;
  margin-bottom: 24px;
}
.article-meta .author {
  font-weight: bolder;
  color: #222;
}
.split-line {
  height: 1px;
  background: #e8e8e8;
  margin-bottom: 24px;
}
.article-content {
  font-size: 18px;
  color: #333;
  line-height: 1.8;
  padding-bottom: 100px;
  text-align: left;
}

.rich-content {
  font-size: 18px;
  line-height: 1.9;
  color: #2b2b2b;
  word-break: break-word;
}

.rich-content :deep(p) {
  margin: 0 0 1em;
}

.rich-content :deep(h1),
.rich-content :deep(h2),
.rich-content :deep(h3) {
  margin: 1.2em 0 0.6em;
  line-height: 1.4;
  color: #1f1f1f;
}

.rich-content :deep(blockquote) {
  margin: 1em 0;
  padding: 10px 14px;
  border-left: 4px solid #f04142;
  background: #fff4f4;
  color: #444;
}

.rich-content :deep(ul),
.rich-content :deep(ol) {
  padding-left: 1.4em;
  margin: 0.8em 0;
}

.rich-content :deep(pre) {
  overflow-x: auto;
  padding: 12px;
  border-radius: 8px;
  background: #f6f8fa;
}

.rich-content :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.rich-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  margin: 14px 0;
}

.rich-content :deep(a) {
  color: #1559d6;
  text-decoration: underline;
}
.article-cover {
  width: 100%;
  max-height: 400px;
  object-fit: cover;
  border-radius: 6px;
  margin-bottom: 20px;
}

/* ================= 底部相关推荐 ================= */
.related-recommendation {
  margin-top: 40px;
  border-top: 2px solid #f4f5f6;
  padding-top: 20px;
}
.recommend-header h3 {
  font-size: 20px;
  color: #222;
  margin-bottom: 16px;
  border-left: 4px solid #f04142;
  padding-left: 10px;
}

/* 复用Home页面的卡片样式 */
.news-card {
  display: flex;
  align-items: stretch;
  gap: 16px;
  padding: 16px 0;
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
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
}
.news-desc {
  font-size: 14px;
  color: #555;
  margin: 0 0 12px 0;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  overflow: hidden;
  text-overflow: ellipsis;
  text-align: left;
}
.news-meta {
  font-size: 13px;
  color: #777;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
}

/* 3. 右侧边栏 */
.right-sidebar {
  width: 320px;
  flex-shrink: 0;
}

.summary-float-trigger {
  position: absolute;
  right: -68px;
  top: 128px;
  border: 1px solid #93c5fd;
  background: #dbeafe;
  color: #1e3a8a;
  padding: 18px 12px;
  border-radius: 10px;
  writing-mode: vertical-rl;
  text-orientation: mixed;
  font-weight: 900;
  font-size: 18px;
  letter-spacing: 2px;
  cursor: pointer;
}
.author-card {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 6px;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.author-info {
  display: flex;
  align-items: center;
  gap: 12px;
}
.avatar {
  width: 50px;
  height: 50px;
  background: #f04142;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: bold;
}
.name-box .name {
  font-size: 16px;
  font-weight: bold;
  color: #222;
}
.name-box .desc {
  font-size: 13px;
  color: #999;
  margin-top: 4px;
}
.follow-btn {
  background: #f04142;
  color: white;
  border: none;
  padding: 6px 20px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.loading-tip, .error-tip {
  text-align: center;
  padding: 100px;
  color: #999;
  font-size: 18px;
}

.summary-chat-window {
  position: fixed;
  right: 24px;
  top: 168px;
  width: min(600px, 48vw);
  height: min(80vh, 950px);
  z-index: 1200;
}

.summary-drawer {
  width: 100%;
  height: 100%;
  background: #fff;
  box-shadow: 0 20px 30px rgba(15, 23, 42, 0.24);
  border-radius: 14px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  text-align: left;
  padding: 15px;
}

.summary-drawer header {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: flex-start;
  padding: 16px;
  border-bottom: 1px solid #e5e7eb;
}

.summary-drawer h3 {
  margin: 0;
}

.summary-drawer header p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.45;
}

.summary-close {
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #111827;
  border-radius: 8px;
  width: 34px;
  height: 34px;
  font-size: 22px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  cursor: pointer;
}

.summary-body {
  flex: 1;
  overflow: auto;
  padding: 16px;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
  text-align: left;
}

.summary-loading {
  color: #334155;
}

.summary-error {
  color: #b91c1c;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  padding: 10px;
}

.summary-chat-item {
  background: #fff;
  border: 1px solid #dbe3ef;
  border-radius: 10px;
  padding: 10px;
  margin-bottom: 10px;
}

.summary-chat-item.user {
  background: #eef6ff;
  border-color: #bfd8ff;
}

.summary-chat-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
  color: #64748b;
  font-size: 12px;
}

.summary-chat-model {
  color: #2563eb;
}

.summary-chat-content {
  color: #334155;
  line-height: 1.65;
  word-break: break-word;
}

.summary-chat-content :deep(*) {
  text-align: left;
}

.summary-chat-content.plain {
  white-space: pre-wrap;
}

.summary-composer {
  margin-top: 12px;
  border-top: 1px solid #e2e8f0;
  padding-top: 12px;
}

.summary-composer textarea {
  width: 100%;
  border: 1px solid #cbd5e1;
  background: #f1f5f9;
  color: #111827;
  border-radius: 8px;
  resize: vertical;
  padding: 10px;
  font-size: 14px;
}

.summary-composer button {
  margin-top: 8px;
  border: none;
  background: #1d4ed8;
  color: #fff;
  border-radius: 8px;
  height: 34px;
  padding: 0 14px;
  cursor: pointer;
}

@media (max-width: 1240px) {
  .summary-float-trigger {
    right: 0;
  }
}

@media (max-width: 900px) {
  .summary-chat-window {
    right: 8px;
    left: 8px;
    width: auto;
    top: 148px;
    height: 66vh;
  }
}
</style>