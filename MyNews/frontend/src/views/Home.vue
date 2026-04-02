<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
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

/* 登录相关样式 */
</style>
