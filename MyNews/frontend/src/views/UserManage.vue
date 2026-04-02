<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import TopNavBar from '../components/TopNavBar.vue'
import { useTopNavAuth } from '../composables/useTopNavAuth'
import { API_BASE_URL, withApiBase } from '../config/api'

const router = useRouter()
const {
  currentUser,
  restoreCurrentUser,
  logout,
  goHome,
  goToProfile,
  handlePublishClick,
  ensureAuthenticated,
} = useTopNavAuth()

const currentPane = ref('users')
const newsPane = ref('pending')
const BACKEND_BUFFER_SIZE = 50

const loadingUsers = ref(false)
const loadingNews = ref(false)
const submitting = ref(false)
const loadingDetail = ref(false)
const message = ref('')
const toastVisible = ref(false)
const toastMessage = ref('')
const detailVisible = ref(false)
const detailError = ref('')
const detailSummary = ref(null)
const detailData = ref(null)
let toastTimer = null

const users = ref([])
const roleDraft = ref({})
const userPage = ref(1)
const userPageSize = ref(8)
const userBackendPage = ref(0)
const userHasMore = ref(true)

const categories = ref([])
const pendingNewsList = ref([])
const reviewedNewsList = ref([])
const newsCategoryDraft = ref({})
const rejectReasonDraft = ref({})
const pendingNewsPage = ref(1)
const reviewedNewsPage = ref(1)
const newsPageSize = ref(6)
const pendingNewsBackendPage = ref(0)
const approvedNewsBackendPage = ref(0)
const rejectedNewsBackendPage = ref(0)
const pendingNewsHasMore = ref(true)
const approvedNewsHasMore = ref(true)
const rejectedNewsHasMore = ref(true)
const pendingNewsTotal = ref(0)
const approvedNewsTotal = ref(0)
const rejectedNewsTotal = ref(0)

const manageableUsers = computed(() => users.value.filter((item) => item.role !== 'admin'))
const adminUsers = computed(() => users.value.filter((item) => item.role === 'admin'))

const displayedNews = computed(() => (newsPane.value === 'pending' ? pendingNewsList.value : reviewedNewsList.value))
const totalUserPages = computed(() => Math.max(1, Math.ceil(manageableUsers.value.length / userPageSize.value)))
const pagedUsers = computed(() => {
  const start = (userPage.value - 1) * userPageSize.value
  return manageableUsers.value.slice(start, start + userPageSize.value)
})
const currentNewsPage = computed(() => (newsPane.value === 'pending' ? pendingNewsPage.value : reviewedNewsPage.value))
const totalNewsPages = computed(() => Math.max(1, Math.ceil(displayedNews.value.length / newsPageSize.value)))
const pagedDisplayedNews = computed(() => {
  const start = (currentNewsPage.value - 1) * newsPageSize.value
  return displayedNews.value.slice(start, start + newsPageSize.value)
})
const reviewedHasMore = computed(() => approvedNewsHasMore.value || rejectedNewsHasMore.value)
const reviewedNewsTotal = computed(() => approvedNewsTotal.value + rejectedNewsTotal.value)

const roleOptions = [
  { label: '普通用户', value: 'user' },
  { label: '审核员', value: 'reviewer' },
]

const showError = (error, fallback = '请求失败，请稍后重试。') => {
  message.value = error?.response?.data?.message || error?.response?.data?.detail || fallback
}

const showSuccessToast = (text) => {
  toastMessage.value = text
  toastVisible.value = true
  if (toastTimer) {
    clearTimeout(toastTimer)
  }
  toastTimer = setTimeout(() => {
    toastVisible.value = false
    toastMessage.value = ''
    toastTimer = null
  }, 1800)
}

const escapeHtml = (raw) => {
  return raw
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

const handlePublishClickFromNav = () => {
  handlePublishClick({ openLoginModal: () => router.push('/') })
}

const normalizeImageUrl = (url) => {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  if (url.startsWith('/')) return `${API_BASE_URL}${url}`
  return `${API_BASE_URL}/${url}`
}

const formatDateTime = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

const openNewsDetailDrawer = async (item) => {
  detailVisible.value = true
  detailError.value = ''
  detailSummary.value = item
  detailData.value = null
  loadingDetail.value = true

  try {
    const res = await axios.get(withApiBase(`/news/detail/${item.id}`))
    if (res.data?.code === 200) {
      detailData.value = res.data.data || null
      return
    }
    detailError.value = res.data?.message || '拉取新闻详情失败。'
  } catch (error) {
    detailError.value = error?.response?.data?.message || error?.response?.data?.detail || '拉取新闻详情失败。'
  } finally {
    loadingDetail.value = false
  }
}

const closeNewsDetailDrawer = () => {
  detailVisible.value = false
  detailError.value = ''
}

const detailTitle = computed(() => detailData.value?.title || detailSummary.value?.title || '新闻详情')
const detailAuthor = computed(() => detailData.value?.author || detailSummary.value?.author || '匿名')
const detailCategoryName = computed(() => detailSummary.value?.category_name || '-')
const detailPublishTime = computed(() => formatDateTime(detailSummary.value?.publish_time || detailData.value?.publish_time))
const detailViews = computed(() => detailData.value?.views ?? detailSummary.value?.views ?? 0)
const detailContentHtml = computed(() => {
  const raw = detailData.value?.content || ''
  if (!raw.trim()) {
    return '<p>暂无正文内容</p>'
  }
  if (/<\/?[a-z][\s\S]*>/i.test(raw)) {
    return raw
  }
  return `<p>${escapeHtml(raw).replaceAll('\n', '<br>')}</p>`
})
const detailImage = computed(() => detailData.value?.image || detailSummary.value?.image || '')
const detailAuditStatus = computed(() => detailSummary.value?.audit_status || detailData.value?.audit_status || '-')
const detailAuditRemark = computed(() => detailSummary.value?.audit_remark || detailData.value?.audit_remark || '无')
const detailAuditor = computed(() => detailSummary.value?.audited_by_user_id || detailData.value?.audited_by_user_id || '-')
const detailAuditedAt = computed(() => {
  const raw = detailSummary.value?.audited_at || detailData.value?.audited_at
  return raw ? formatDateTime(raw) : '-'
})

const ensureUserPageInRange = () => {
  userPage.value = Math.min(Math.max(1, userPage.value), totalUserPages.value)
}

const ensureNewsPageInRange = (pane = newsPane.value) => {
  const list = pane === 'pending' ? pendingNewsList.value : reviewedNewsList.value
  const total = Math.max(1, Math.ceil(list.length / newsPageSize.value))
  if (pane === 'pending') {
    pendingNewsPage.value = Math.min(Math.max(1, pendingNewsPage.value), total)
    return
  }
  reviewedNewsPage.value = Math.min(Math.max(1, reviewedNewsPage.value), total)
}

const prevUserPage = () => {
  if (userPage.value > 1) userPage.value -= 1
}

const fillUserTailPageIfNeeded = async () => {
  const isTailPage = userPage.value === totalUserPages.value
  const currentCount = pagedUsers.value.length
  if (isTailPage && currentCount > 0 && currentCount < userPageSize.value && userHasMore.value) {
    await fetchUsers()
  }
}

const nextUserPage = async () => {
  if (userPage.value < totalUserPages.value) {
    userPage.value += 1
    await fillUserTailPageIfNeeded()
    return
  }

  if (userHasMore.value) {
    await fetchUsers()
  }
}

const fillNewsTailPageIfNeeded = async (pane = newsPane.value) => {
  const list = pane === 'pending' ? pendingNewsList.value : reviewedNewsList.value
  const page = pane === 'pending' ? pendingNewsPage.value : reviewedNewsPage.value
  const hasMore = pane === 'pending' ? pendingNewsHasMore.value : reviewedHasMore.value
  const total = Math.max(1, Math.ceil(list.length / newsPageSize.value))
  const start = (page - 1) * newsPageSize.value
  const currentCount = list.slice(start, start + newsPageSize.value).length
  const isTailPage = page === total
  if (isTailPage && currentCount > 0 && currentCount < newsPageSize.value && hasMore) {
    await fetchNews({ reset: false })
  }
}

const setNewsPane = async (pane) => {
  newsPane.value = pane
  ensureNewsPageInRange(pane)
  await fillNewsTailPageIfNeeded(pane)
}

const prevNewsPage = () => {
  if (newsPane.value === 'pending') {
    if (pendingNewsPage.value > 1) pendingNewsPage.value -= 1
    return
  }
  if (reviewedNewsPage.value > 1) reviewedNewsPage.value -= 1
}

const nextNewsPage = async () => {
  if (newsPane.value === 'pending') {
    const total = Math.max(1, Math.ceil(pendingNewsList.value.length / newsPageSize.value))
    if (pendingNewsPage.value < total) {
      pendingNewsPage.value += 1
      await fillNewsTailPageIfNeeded('pending')
      return
    }
    if (pendingNewsHasMore.value) {
      await fetchNews({ reset: false })
    }
    return
  }
  const total = Math.max(1, Math.ceil(reviewedNewsList.value.length / newsPageSize.value))
  if (reviewedNewsPage.value < total) {
    reviewedNewsPage.value += 1
    await fillNewsTailPageIfNeeded('reviewed')
    return
  }
  if (reviewedHasMore.value) {
    await fetchNews({ reset: false })
  }
}

const normalizeNewsDraft = () => {
  const categoryDraft = {}
  const reasonDraft = {}
  ;[...pendingNewsList.value, ...reviewedNewsList.value].forEach((item) => {
    categoryDraft[item.id] = item.category_id
    reasonDraft[item.id] = item.audit_remark || ''
  })
  newsCategoryDraft.value = categoryDraft
  rejectReasonDraft.value = reasonDraft
}

const initRoleDraft = () => {
  const next = {}
  manageableUsers.value.forEach((item) => {
    next[item.id] = item.role
  })
  roleDraft.value = next
}

const mergeUniqueById = (source, incoming) => {
  const map = new Map(source.map((item) => [item.id, item]))
  incoming.forEach((item) => {
    map.set(item.id, item)
  })
  return Array.from(map.values())
}

const fetchUsers = async ({ reset = false } = {}) => {
  if (!reset && (!userHasMore.value || loadingUsers.value)) {
    return
  }

  loadingUsers.value = true
  message.value = ''
  try {
    const nextBackendPage = reset ? 1 : userBackendPage.value + 1
    const skip = (nextBackendPage - 1) * BACKEND_BUFFER_SIZE
    const res = await axios.get(withApiBase(`/users/admin?skip=${skip}&limit=${BACKEND_BUFFER_SIZE}`))
    if (res.data?.code === 200) {
      const incoming = res.data.data || []
      users.value = reset ? incoming : mergeUniqueById(users.value, incoming)
      userBackendPage.value = nextBackendPage
      userHasMore.value = incoming.length === BACKEND_BUFFER_SIZE
      initRoleDraft()
      ensureUserPageInRange()
      return
    }
    message.value = res.data?.message || '拉取用户列表失败。'
  } catch (error) {
    showError(error, '拉取用户列表失败。')
  } finally {
    loadingUsers.value = false
  }
}

const fetchCategories = async () => {
  try {
    const res = await axios.get(withApiBase('/news/categories?skip=0&limit=100'))
    if (res.data?.code === 200) {
      categories.value = res.data.data || []
      return
    }
    message.value = res.data?.message || '拉取分类失败。'
  } catch (error) {
    showError(error, '拉取分类失败。')
  }
}

const fetchNewsByStatus = async (status, page = 1) => {
  const res = await axios.get(withApiBase(`/news/admin/list?page=${page}&size=${BACKEND_BUFFER_SIZE}&audit_status=${status}`))
  if (res.data?.code === 200) {
    return {
      items: res.data?.data?.items || [],
      total: Number(res.data?.data?.total || 0),
    }
  }
  return {
    items: [],
    total: 0,
  }
}

const fetchPendingNewsBuffer = async ({ reset = false } = {}) => {
  if (!reset && !pendingNewsHasMore.value) {
    return
  }

  const nextPage = reset ? 1 : pendingNewsBackendPage.value + 1
  const result = await fetchNewsByStatus('pending', nextPage)
  const incoming = result.items
  pendingNewsList.value = reset ? incoming : mergeUniqueById(pendingNewsList.value, incoming)
  pendingNewsBackendPage.value = nextPage
  pendingNewsHasMore.value = incoming.length === BACKEND_BUFFER_SIZE
  pendingNewsTotal.value = result.total
}

const fetchReviewedNewsBuffer = async ({ reset = false } = {}) => {
  const shouldFetchApproved = reset || approvedNewsHasMore.value
  const shouldFetchRejected = reset || rejectedNewsHasMore.value
  if (!shouldFetchApproved && !shouldFetchRejected) {
    return
  }

  const approvedPage = reset ? 1 : approvedNewsBackendPage.value + 1
  const rejectedPage = reset ? 1 : rejectedNewsBackendPage.value + 1

  const [approvedResult, rejectedResult] = await Promise.all([
    shouldFetchApproved
      ? fetchNewsByStatus('approved', approvedPage)
      : Promise.resolve({ items: [], total: approvedNewsTotal.value }),
    shouldFetchRejected
      ? fetchNewsByStatus('rejected', rejectedPage)
      : Promise.resolve({ items: [], total: rejectedNewsTotal.value }),
  ])

  const approvedIncoming = approvedResult.items || []
  const rejectedIncoming = rejectedResult.items || []

  const reviewedIncoming = [...approvedIncoming, ...rejectedIncoming]
  reviewedNewsList.value = reset ? reviewedIncoming : mergeUniqueById(reviewedNewsList.value, reviewedIncoming)
  reviewedNewsList.value.sort((a, b) => new Date(b.publish_time).getTime() - new Date(a.publish_time).getTime())

  if (shouldFetchApproved) {
    approvedNewsBackendPage.value = approvedPage
    approvedNewsHasMore.value = approvedIncoming.length === BACKEND_BUFFER_SIZE
    approvedNewsTotal.value = Number(approvedResult.total || 0)
  }
  if (shouldFetchRejected) {
    rejectedNewsBackendPage.value = rejectedPage
    rejectedNewsHasMore.value = rejectedIncoming.length === BACKEND_BUFFER_SIZE
    rejectedNewsTotal.value = Number(rejectedResult.total || 0)
  }
}

const fetchNews = async ({ reset = false } = {}) => {
  loadingNews.value = true
  message.value = ''
  try {
    if (reset) {
      pendingNewsList.value = []
      reviewedNewsList.value = []
      pendingNewsBackendPage.value = 0
      approvedNewsBackendPage.value = 0
      rejectedNewsBackendPage.value = 0
      pendingNewsHasMore.value = true
      approvedNewsHasMore.value = true
      rejectedNewsHasMore.value = true
      pendingNewsTotal.value = 0
      approvedNewsTotal.value = 0
      rejectedNewsTotal.value = 0
      pendingNewsPage.value = 1
      reviewedNewsPage.value = 1
    }

    await Promise.all([
      fetchPendingNewsBuffer({ reset }),
      fetchReviewedNewsBuffer({ reset }),
    ])

    normalizeNewsDraft()
    ensureNewsPageInRange('pending')
    ensureNewsPageInRange('reviewed')
  } catch (error) {
    showError(error, '拉取新闻管理列表失败。')
  } finally {
    loadingNews.value = false
  }
}

const refreshCurrentPane = async () => {
  if (currentPane.value === 'users') {
    userBackendPage.value = 0
    userHasMore.value = true
    userPage.value = 1
    await fetchUsers({ reset: true })
    return
  }
  await fetchNews({ reset: true })
}

const updateUserRole = async (target) => {
  const nextRole = roleDraft.value[target.id]
  if (!nextRole || nextRole === target.role) return

  submitting.value = true
  message.value = ''
  try {
    const res = await axios.patch(withApiBase(`/users/admin/${target.id}/role`), { role: nextRole })
    if (res.data?.code === 200) {
      target.role = nextRole
      showSuccessToast(`已更新 ${target.username} 的角色`)
      return
    }
    message.value = res.data?.message || '角色更新失败。'
    roleDraft.value[target.id] = target.role
  } catch (error) {
    roleDraft.value[target.id] = target.role
    showError(error, '角色更新失败。')
  } finally {
    submitting.value = false
  }
}

const toggleUserStatus = async (target) => {
  const nextStatus = target.status === 'active' ? 'disabled' : 'active'

  submitting.value = true
  message.value = ''
  try {
    const res = await axios.patch(withApiBase(`/users/admin/${target.id}/status`), { status: nextStatus })
    if (res.data?.code === 200) {
      target.status = nextStatus
      showSuccessToast(`已${nextStatus === 'active' ? '启用' : '禁用'} ${target.username}`)
      return
    }
    message.value = res.data?.message || '状态更新失败。'
  } catch (error) {
    showError(error, '状态更新失败。')
  } finally {
    submitting.value = false
  }
}

const buildModerationPayload = (item, extra = {}) => {
  const draftCategoryId = Number(newsCategoryDraft.value[item.id] || item.category_id)
  const payload = {
    category_id: Number.isNaN(draftCategoryId) ? item.category_id : draftCategoryId,
    ...extra,
  }
  return payload
}

const updateNewsCategory = async (item) => {
  submitting.value = true
  message.value = ''
  try {
    const payload = buildModerationPayload(item)
    const res = await axios.patch(withApiBase(`/news/admin/${item.id}/moderation`), payload)
    if (res.data?.code === 200) {
      showSuccessToast(`已更新《${item.title}》分类`)
      await fetchNews()
      return
    }
    message.value = res.data?.message || '分类更新失败。'
  } catch (error) {
    showError(error, '分类更新失败。')
  } finally {
    submitting.value = false
  }
}

const approveNews = async (item) => {
  submitting.value = true
  message.value = ''
  try {
    const payload = buildModerationPayload(item, { audit_status: 'approved' })
    const res = await axios.patch(withApiBase(`/news/admin/${item.id}/moderation`), payload)
    if (res.data?.code === 200) {
      showSuccessToast(`已通过《${item.title}》审核`)
      await fetchNews()
      return
    }
    message.value = res.data?.message || '审核通过失败。'
  } catch (error) {
    showError(error, '审核通过失败。')
  } finally {
    submitting.value = false
  }
}

const rejectNews = async (item) => {
  const reason = (rejectReasonDraft.value[item.id] || '').trim()
  if (!reason) {
    message.value = '拒绝审核时请填写拒绝原因。'
    return
  }

  submitting.value = true
  message.value = ''
  try {
    const payload = buildModerationPayload(item, {
      audit_status: 'rejected',
      audit_remark: reason,
    })
    const res = await axios.patch(withApiBase(`/news/admin/${item.id}/moderation`), payload)
    if (res.data?.code === 200) {
      showSuccessToast(`已拒绝《${item.title}》并记录原因`)
      await fetchNews()
      return
    }
    message.value = res.data?.message || '拒绝审核失败。'
  } catch (error) {
    showError(error, '拒绝审核失败。')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  restoreCurrentUser()
  if (!ensureAuthenticated('/')) {
    return
  }
  if (currentUser.value?.role !== 'admin') {
    router.replace('/profile')
    return
  }

  userBackendPage.value = 0
  userHasMore.value = true
  await Promise.all([fetchUsers({ reset: true }), fetchCategories(), fetchNews({ reset: true })])
})

onBeforeUnmount(() => {
  if (toastTimer) {
    clearTimeout(toastTimer)
    toastTimer = null
  }
})
</script>

<template>
  <div class="manage-layout">
    <TopNavBar
      :current-user="currentUser"
      @logo-click="goHome"
      @profile-click="goToProfile"
      @logout-click="logout"
      @publish-click="handlePublishClickFromNav"
      @login-click="goHome"
    />

    <main class="manage-main">
      <section class="manage-hero">
        <div class="hero-content">
          <h1>后台管理中心</h1>
          <p>管理员可在此管理用户账号与新闻审核流程。</p>
        </div>
        <button class="refresh-btn" :disabled="submitting || loadingUsers || loadingNews" @click="refreshCurrentPane">
            <svg t="1775102124981" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="4793" data-spm-anchor-id="a313x.search_index.0.i0.3bb43a81mRVj4Y" width="15" height="15"><path d="M960 630.4c-12.8-3.2-25.6 3.2-32 12.8-76.8 204.8-320 307.2-544 227.2-224-80-342.4-307.2-265.6-512 76.8-204.8 320-307.2 544-227.2 92.8 32 172.8 92.8 224 172.8l-92.8 0c-12.8 0-25.6 9.6-25.6 22.4 0 12.8 9.6 22.4 25.6 22.4l153.6 0c12.8 0 25.6-9.6 25.6-22.4l0-140.8c0-12.8-9.6-22.4-25.6-22.4-12.8 0-25.6 9.6-25.6 22.4l0 89.6c-57.6-86.4-140.8-150.4-246.4-188.8-249.6-86.4-518.4 28.8-608 256-86.4 230.4 44.8 486.4 294.4 572.8 249.6 86.4 518.4-28.8 608-256C979.2 649.6 972.8 636.8 960 630.4z" p-id="4794"></path></svg>
        </button>
      </section>

      <nav class="manage-nav-bar">
        <button
          class="manage-nav-item"
          :class="{ active: currentPane === 'users' }"
          @click="currentPane = 'users'"
        >
          用户管理
        </button>
        <button
          class="manage-nav-item"
          :class="{ active: currentPane === 'news' }"
          @click="currentPane = 'news'"
        >
          新闻管理
        </button>
      </nav>

      <p v-if="message" class="message">{{ message }}</p>

      <section v-if="currentPane === 'users'" class="panel">
        <h2>可管理账号（{{ manageableUsers.length }}）</h2>
        <div v-if="loadingUsers" class="placeholder">正在加载用户列表...</div>
        <div v-else-if="manageableUsers.length === 0" class="placeholder">暂无可管理账号。</div>

        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>用户名</th>
                <th>昵称</th>
                <th>角色</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in pagedUsers" :key="item.id">
                <td>{{ item.id }}</td>
                <td>{{ item.username }}</td>
                <td>{{ item.nickname || '-' }}</td>
                <td>
                  <select v-model="roleDraft[item.id]" :disabled="submitting">
                    <option v-for="opt in roleOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                  </select>
                </td>
                <td>
                  <span class="status-badge" :class="item.status">{{ item.status === 'active' ? '启用' : '禁用' }}</span>
                </td>
                <td class="actions">
                  <button :disabled="submitting" @click="updateUserRole(item)">保存角色</button>
                  <button :disabled="submitting" @click="toggleUserStatus(item)">
                    {{ item.status === 'active' ? '禁用账号' : '启用账号' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="admin-box">
          <h3>管理员账号（{{ adminUsers.length }}）</h3>
          <p>管理员账号不在此模块管理，避免误操作影响后台可用性。</p>
        </div>

        <div v-if="manageableUsers.length > 0" class="pager">
          <button :disabled="userPage <= 1" @click="prevUserPage">上一页</button>
          <span>第 {{ userPage }} / {{ totalUserPages }} 页</span>
          <button :disabled="userPage >= totalUserPages && !userHasMore" @click="nextUserPage">下一页</button>
        </div>
      </section>

      <section v-else class="panel">
        <div class="news-head">
          <h2>新闻管理</h2>
          <div class="news-filter">
            <button
              class="news-tab"
              :class="{ active: newsPane === 'pending' }"
              @click="setNewsPane('pending')"
            >
              未审核（{{ pendingNewsTotal }}）
            </button>
            <button
              class="news-tab"
              :class="{ active: newsPane === 'reviewed' }"
              @click="setNewsPane('reviewed')"
            >
              已审核（{{ reviewedNewsTotal }}）
            </button>
          </div>
        </div>

        <div v-if="loadingNews" class="placeholder">正在加载新闻审核列表...</div>
        <div v-else-if="displayedNews.length === 0" class="placeholder">当前分组暂无新闻。</div>

        <div v-else class="news-cards">
          <article class="news-card" v-for="item in pagedDisplayedNews" :key="item.id">
            <div class="news-top">
              <button class="news-title-link" type="button" @click="openNewsDetailDrawer(item)">{{ item.title }}</button>
              <span class="audit-badge" :class="item.audit_status">{{ item.audit_status }}</span>
            </div>
            <p class="meta">作者：{{ item.author || '匿名' }} ｜ 分类：{{ item.category_name }} ｜ 阅读：{{ item.views }}</p>
            <p class="desc">{{ item.description || '暂无摘要' }}</p>

            <div class="editor-row">
              <label>分类调整</label>
              <select v-model="newsCategoryDraft[item.id]" :disabled="submitting">
                <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option>
              </select>
              <button :disabled="submitting" @click="updateNewsCategory(item)">保存分类</button>
            </div>

            <div class="editor-row reject-row">
              <label>拒绝原因</label>
              <input
                v-model="rejectReasonDraft[item.id]"
                :disabled="submitting"
                type="text"
                maxlength="500"
                placeholder="拒绝审核时请填写原因"
              />
            </div>

            <div class="action-row">
              <button class="approve-btn" :disabled="submitting" @click="approveNews(item)">通过审核</button>
              <button class="reject-btn" :disabled="submitting" @click="rejectNews(item)">拒绝审核</button>
            </div>
          </article>

          <div class="pager">
            <button :disabled="currentNewsPage <= 1" @click="prevNewsPage">上一页</button>
            <span>第 {{ currentNewsPage }} / {{ totalNewsPages }} 页</span>
            <button :disabled="currentNewsPage >= totalNewsPages && !(newsPane === 'pending' ? pendingNewsHasMore : reviewedHasMore)" @click="nextNewsPage">下一页</button>
          </div>
        </div>
      </section>
    </main>

    <transition name="toast-fade">
      <div v-if="toastVisible" class="light-toast">{{ toastMessage }}</div>
    </transition>

    <transition name="drawer-fade">
      <div v-if="detailVisible" class="detail-overlay" @click="closeNewsDetailDrawer"></div>
    </transition>

    <transition name="drawer-slide">
      <aside v-if="detailVisible" class="detail-drawer">
        <div class="detail-header">
          <h3>审核详情</h3>
          <button class="drawer-close" type="button" @click="closeNewsDetailDrawer">关闭</button>
        </div>

        <div class="detail-body">
          <div v-if="loadingDetail" class="placeholder">正在加载正文详情...</div>
          <div v-else>
            <p v-if="detailError" class="detail-error">{{ detailError }}</p>

            <h4 class="detail-title">{{ detailTitle }}</h4>
            <p class="detail-meta">作者：{{ detailAuthor }} ｜ 分类：{{ detailCategoryName }}</p>
            <p class="detail-meta">发布时间：{{ detailPublishTime }} ｜ 阅读：{{ detailViews }}</p>

            <img v-if="detailImage" class="detail-image" :src="normalizeImageUrl(detailImage)" alt="news-cover" />

            <div class="detail-content" v-html="detailContentHtml"></div>

            <section class="audit-record-card">
              <h5>审核记录</h5>
              <p>审核状态：<strong>{{ detailAuditStatus }}</strong></p>
              <p>拒绝原因：{{ detailAuditRemark }}</p>
              <p>审核人ID：{{ detailAuditor }}</p>
              <p>审核时间：{{ detailAuditedAt }}</p>
            </section>
          </div>
        </div>
      </aside>
    </transition>
  </div>
</template>

<style scoped>
.manage-layout {
  min-height: 100vh;
  background: #f4f6fa;
}

.manage-main {
  width: min(1200px, 100%);
  margin: 76px auto 0;
  padding: 20px 16px 40px;
  box-sizing: border-box;
}

.manage-hero {
  border-radius: 14px;
  padding: 20px;
  color: #fff;
  background: linear-gradient(130deg, #ca2f32, #f27c28);
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
}
.hero-content{
    text-align: left;

}
.hero-content h1 {
  margin: 10px 0 10px;
  font-size: 28px;

}

.hero-content p {
  margin: 8px 0 0;
  opacity: 0.92;
  font-size: 16px;
}

.manage-nav-bar {
  margin-top: 12px;
  background: #ffffff;
  border: 1px solid #e7ebf0;
  border-radius: 10px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  overflow: hidden;
}

.manage-nav-item {
  height: 44px;
  border: none;
  background: #fff;
  color: #334155;
  cursor: pointer;
  font-size: 15px;
  font-weight: 600;
}

.manage-nav-item.active {
  background: #e5e7eb;
  color: #1f2937;
}

.refresh-btn {
  border: 1px solid rgba(255, 255, 255, 0.5);
  background: rgba(15, 23, 42, 0.28);
  color: #fff;
  border-radius: 999px;
  padding: 8px 14px;
  cursor: pointer;
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.message {
  margin: 14px 0 0;
  color: #c0262d;
}

.panel {
  margin-top: 14px;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #eceff4;
  box-shadow: 0 6px 22px rgba(15, 23, 42, 0.04);
  padding: 16px;
}

.panel h2 {
  margin: 0 0 10px;
  font-size: 18px;
  text-align: left;
  color: #1f2937;
}

.placeholder {
  padding: 24px;
  color: #64748b;
  text-align: center;
}

.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th,
td {
  border-bottom: 1px solid #edf1f5;
  padding: 10px;
  text-align: left;
  font-size: 14px;
}

th {
  color: #475569;
  background: #f8fafc;
}

select,
input {
  height: 34px;
  border-radius: 8px;
  border: 1px solid #dbe2ea;
  padding: 0 8px;
  background: #f1f5f9;
  color: #1f2937;
}

.status-badge {
  display: inline-flex;
  border-radius: 999px;
  font-size: 12px;
  padding: 2px 10px;
}

.status-badge.active {
  color: #166534;
  background: #dcfce7;
}

.status-badge.disabled {
  color: #9f1239;
  background: #ffe4e6;
}

.actions {
  display: flex;
  gap: 8px;
}

.actions button {
  border: 1px solid #d7dee7;
  background: #fff;
  color: #334155;
  border-radius: 8px;
  height: 32px;
  padding: 0 10px;
  cursor: pointer;
}

.actions button:hover:not(:disabled) {
  border-color: #ca2f32;
  color: #ca2f32;
}

.admin-box {
  margin-top: 12px;
  border-top: 1px dashed #e2e8f0;
  padding-top: 12px;
  text-align: left;
  color: #64748b;
}

.news-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.news-filter {
  display: flex;
  gap: 8px;
}

.news-tab {
  border: 1px solid #d8e0ea;
  background: #f8fafc;
  color: #334155;
  border-radius: 999px;
  height: 34px;
  padding: 0 14px;
  cursor: pointer;
}

.news-tab.active {
  border-color: #d1d5db;
  color: #1f2937;
  background: #e5e7eb;
}

.news-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.news-card {
  border: 1px solid #e7ebf0;
  border-radius: 10px;
  padding: 12px;
  text-align: left;
}

.news-top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}

.news-title-link {
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  color: #111827;
  font-size: 17px;
  text-align: left;
  cursor: pointer;
}

.news-title-link:hover {
  color: #ca2f32;
  text-decoration: underline;
}

.audit-badge {
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
  border: 1px solid #dbe4ee;
}

.audit-badge.pending {
  background: #fff7ed;
  color: #b45309;
  border-color: #fed7aa;
}

.audit-badge.approved {
  background: #ecfdf5;
  color: #166534;
  border-color: #bbf7d0;
}

.audit-badge.rejected {
  background: #fef2f2;
  color: #b91c1c;
  border-color: #fecaca;
}

.meta {
  margin: 8px 0 0;
  color: #6b7280;
  font-size: 13px;
}

.desc {
  margin: 8px 0;
  color: #374151;
}

.editor-row {
  margin-top: 8px;
  display: grid;
  grid-template-columns: 88px 1fr 96px;
  gap: 8px;
  align-items: center;
}

.reject-row {
  grid-template-columns: 88px 1fr;
}

.editor-row label {
  color: #6b7280;
  font-size: 13px;
}

.editor-row button {
  height: 34px;
  border-radius: 8px;
  border: 1px solid #dbe2ea;
  background: #e5e7eb;
  color: #334155;
  cursor: pointer;
}

.editor-row button:hover:not(:disabled) {
  border-color: #cbd5e1;
  color: #111827;
}

.action-row {
  margin-top: 10px;
  display: flex;
  gap: 8px;
}

.action-row button {
  border: none;
  border-radius: 8px;
  height: 34px;
  padding: 0 14px;
  color: #fff;
  cursor: pointer;
}

.approve-btn {
  background: #15803d;
}

.reject-btn {
  background: #b91c1c;
}

.light-toast {
  position: fixed;
  left: 50%;
  bottom: 80px;
  transform: translateX(-50%);
  z-index: 1200;
  background: rgba(34, 197, 94, 0.72);
  color: #f0fdf4;
  border: 1px solid rgba(187, 247, 208, 0.85);
  border-radius: 10px;
  padding: 10px 16px;
  box-shadow: 0 8px 24px rgba(22, 101, 52, 0.25);
  backdrop-filter: blur(2px);
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.28s ease, transform 0.28s ease;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}

.detail-overlay {
  position: fixed;
  inset: 0;
  z-index: 1250;
  background: rgba(2, 6, 23, 0.24);
}

.detail-drawer {
  position: fixed;
  top: 0;
  right: 0;
  z-index: 1300;
  width: min(520px, 92vw);
  height: 100vh;
  background: #ffffff;
  box-shadow: -8px 0 30px rgba(15, 23, 42, 0.18);
  display: flex;
  flex-direction: column;
}

.detail-header {
  height: 58px;
  padding: 0 16px;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.detail-header h3 {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
}

.drawer-close {
  border: 1px solid #d1d5db;
  background: #f3f4f6;
  color: #374151;
  border-radius: 8px;
  height: 34px;
  padding: 0 12px;
  cursor: pointer;
}

.detail-body {
  padding: 16px;
  overflow-y: auto;
  text-align: left;
}

.detail-title {
  margin: 0;
  color: #111827;
  font-size: 22px;
  line-height: 1.35;
}

.detail-meta {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 13px;
}

.detail-image {
  margin-top: 14px;
  width: 100%;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
}

.detail-content {
  margin-top: 14px;
  white-space: pre-wrap;
  line-height: 1.75;
  color: #1f2937;
  font-size: 14px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px;
}

.audit-record-card {
  margin-top: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #f9fafb;
  padding: 12px;
}

.audit-record-card h5 {
  margin: 0 0 10px;
  font-size: 15px;
  color: #111827;
}

.audit-record-card p {
  margin: 6px 0;
  color: #475569;
  font-size: 13px;
}

.detail-error {
  margin: 0 0 12px;
  color: #b91c1c;
}

.pager {
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.pager button {
  border: 1px solid #d1d5db;
  background: #f8fafc;
  color: #334155;
  border-radius: 8px;
  height: 32px;
  padding: 0 12px;
  cursor: pointer;
}

.pager button:hover:not(:disabled) {
  border-color: #94a3b8;
}

.pager span {
  color: #475569;
  font-size: 13px;
}

.drawer-fade-enter-active,
.drawer-fade-leave-active {
  transition: opacity 0.22s ease;
}

.drawer-fade-enter-from,
.drawer-fade-leave-to {
  opacity: 0;
}

.drawer-slide-enter-active,
.drawer-slide-leave-active {
  transition: transform 0.28s ease;
}

.drawer-slide-enter-from,
.drawer-slide-leave-to {
  transform: translateX(100%);
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

@media (max-width: 840px) {
  .manage-hero {
    flex-direction: column;
    align-items: flex-start;
  }

  .news-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .editor-row {
    grid-template-columns: 1fr;
  }
}
</style>
