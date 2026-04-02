<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import TopNavBar from '../components/TopNavBar.vue'
import AuthModal from '../components/AuthModal.vue'
import { useTopNavAuth } from '../composables/useTopNavAuth'
import { API_BASE_URL, withApiBase } from '../config/api'

const API_BASE = API_BASE_URL

const route = useRoute()
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

const showAuthModal = ref(false)
const loading = ref(false)
const errorMsg = ref('')
const results = ref([])
const page = ref(1)
const size = ref(10)
const total = ref(0)

const keyword = computed(() => (route.query.q || '').toString().trim())
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / size.value)))

const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const getHighlightParts = (text) => {
  const source = (text || '').toString()
  const key = keyword.value
  if (!source || !key) {
    return [{ text: source, hit: false }]
  }

  const pattern = new RegExp(`(${escapeRegExp(key)})`, 'ig')
  const chunks = source.split(pattern)
  return chunks
    .filter((chunk) => chunk !== '')
    .map((chunk) => ({
      text: chunk,
      hit: chunk.toLowerCase() === key.toLowerCase(),
    }))
}

const handlePublishClickFromNav = () => {
  handlePublishClick({ openLoginModal: () => { showAuthModal.value = true } })
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

const formatTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

const normalizeImageUrl = (url) => {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  if (url.startsWith('/')) return `${API_BASE}${url}`
  return `${API_BASE}/${url}`
}

const fetchSearchResults = async () => {
  if (!keyword.value) {
    results.value = []
    total.value = 0
    return
  }

  loading.value = true
  errorMsg.value = ''
  try {
    const res = await axios.get(withApiBase('/news/search'), {
      params: {
        q: keyword.value,
        page: page.value,
        size: size.value,
      },
    })

    if (res.data?.code === 200) {
      const data = res.data.data || {}
      results.value = data.items || []
      total.value = data.total || 0
    } else {
      errorMsg.value = '搜索失败，请稍后重试。'
    }
  } catch (error) {
    console.error(error)
    errorMsg.value = '搜索失败，请检查后端服务状态。'
  } finally {
    loading.value = false
  }
}

const changePage = (nextPage) => {
  if (nextPage < 1 || nextPage > totalPages.value || nextPage === page.value) {
    return
  }
  page.value = nextPage
  fetchSearchResults()
}

watch(
  () => route.query.q,
  () => {
    page.value = 1
    fetchSearchResults()
  }
)

onMounted(() => {
  restoreCurrentUser()
  fetchSearchResults()
})
</script>

<template>
  <div class="search-layout">
    <TopNavBar
      :current-user="currentUser"
      @logo-click="goHome"
      @login-click="showAuthModal = true"
      @profile-click="goToProfile"
      @logout-click="logout"
      @publish-click="handlePublishClickFromNav"
    />

    <main class="search-main">
      <section class="result-header">
        <h1>搜索结果</h1>
        <p>关键词："{{ keyword || '未输入关键词' }}"，共找到 {{ total }} 条</p>
      </section>

      <section class="result-panel">
        <div v-if="loading" class="tip">正在检索内容...</div>
        <div v-else-if="errorMsg" class="tip error">{{ errorMsg }}</div>
        <div v-else-if="!keyword" class="tip">请输入关键词后再搜索。</div>
        <div v-else-if="results.length === 0" class="tip">没有匹配结果，换个关键词试试。</div>
        <div v-else class="list-wrap">
          <article
            class="result-item"
            v-for="item in results"
            :key="item.id"
            @click="goToDetail(item.id)"
          >
            <div class="content">
              <h3 class="title">
                <span
                  v-for="(part, idx) in getHighlightParts(item.title)"
                  :key="`title-${item.id}-${idx}`"
                  :class="{ 'highlight-keyword': part.hit }"
                >
                  {{ part.text }}
                </span>
              </h3>
              <p class="desc">
                <span
                  v-for="(part, idx) in getHighlightParts(item.description)"
                  :key="`desc-${item.id}-${idx}`"
                  :class="{ 'highlight-keyword': part.hit }"
                >
                  {{ part.text }}
                </span>
              </p>
              <div class="meta">
                <span>{{ item.category_name }}</span>
                <span>{{ item.author || '匿名作者' }}</span>
                <span>{{ item.views }} 阅读</span>
                <span>相关性 {{ item.relevance }}</span>
                <span>{{ formatTime(item.publish_time) }}</span>
              </div>
            </div>
            <img v-if="item.image" :src="normalizeImageUrl(item.image)" alt="cover" class="cover" />
          </article>

          <div class="pager">
            <button @click="changePage(page - 1)" :disabled="page <= 1">上一页</button>
            <span>{{ page }} / {{ totalPages }}</span>
            <button @click="changePage(page + 1)" :disabled="page >= totalPages">下一页</button>
          </div>
        </div>
      </section>
    </main>

    <AuthModal
      v-model:visible="showAuthModal"
      @success="handleAuthSuccess"
    />
  </div>
</template>

<style scoped>
.search-layout {
  min-height: 100vh;
  background: #f4f5f6;
}

.search-main {
  width: 1170px;
  margin: 76px auto 0;
  padding: 20px 16px 40px;
}

.result-header {
  background: #fff;
  border-radius: 10px;
  padding: 18px 20px;
  text-align: left;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.result-header h1 {
  margin: 0;
  font-size: 24px;
  color: #222;
}

.result-header p {
  margin: 8px 0 0;
  color: #6b7480;
}

.result-panel {
  margin-top: 14px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  padding: 8px 20px 20px;
  text-align: left;
}

.tip {
  text-align: center;
  color: #7f8793;
  padding: 30px 0;
}

.tip.error {
  color: #d93025;
}

.result-item {
  display: flex;
  gap: 14px;
  padding: 16px 0;
  border-bottom: 1px solid #eceff3;
  cursor: pointer;
}

.result-item:hover .title {
  color: #f04142;
}

.content {
  flex: 1;
  min-width: 0;
  text-align: left;
}

.title {
  margin: 0;
  color: #222;
  font-size: 20px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  word-break: break-word;
}

.desc {
  margin: 8px 0 10px;
  color: #5d6672;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  word-break: break-word;
}

.highlight-keyword {
  color: #d93025;
  font-weight: 700;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  color: #8a93a0;
  font-size: 13px;
}

.cover {
  width: 160px;
  height: 104px;
  object-fit: cover;
  border-radius: 6px;
}

.pager {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
  padding-top: 16px;
}

.pager button {
  border: 1px solid #d3d8df;
  background: #fff;
  color: #3e4c5c;
  border-radius: 6px;
  padding: 6px 12px;
  cursor: pointer;
}

.pager button:disabled {
  color: #a5afbb;
  border-color: #e4e8ee;
  cursor: not-allowed;
}

@media (max-width: 1200px) {
  .search-main {
    width: 100%;
  }
}
</style>
