<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import TopNavBar from '../components/TopNavBar.vue'
import { useTopNavAuth } from '../composables/useTopNavAuth'
import { API_BASE_URL, withApiBase } from '../config/api'

const API_BASE = API_BASE_URL

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

const profile = ref({
  id: '',
  username: '',
  nickname: '',
  bio: ''
})
const works = ref([])
const favorites = ref([])
const histories = ref([])
const activeTab = ref('works')
const loadingProfile = ref(false)
const loadingWorks = ref(false)
const loadingFavorites = ref(false)
const loadingHistories = ref(false)
const message = ref('')
const favoriteSelectMode = ref(false)
const selectedFavoriteNewsIds = ref([])
const historySelectMode = ref(false)
const selectedHistoryNewsIds = ref([])
const openedWorksMenuNewsId = ref(null)
const deletingNewsId = ref(null)
const toastMessage = ref('')
const toastVisible = ref(false)
let toastTimer = null

const displayName = computed(() => profile.value.nickname || profile.value.username || '头条用户')
const avatarText = computed(() => (displayName.value || '头').slice(0, 1).toUpperCase())
const profileBio = computed(() => profile.value.bio || '这个人很低调，还没有写简介。')
const canAccessBackOffice = computed(() => ['admin', 'reviewer'].includes(currentUser.value?.role))

const goToAdminUserManage = () => {
  if (!canAccessBackOffice.value) return
  router.push('/admin/users')
}

// 弹窗与编辑状态
const showEditModal = ref(false)
const savingProfile = ref(false)
const editForm = ref({
  nickname: '',
  bio: '',
  password: ''
})

const openEditModal = () => {
  editForm.value = { 
    nickname: profile.value.nickname || '',
    bio: profile.value.bio || '',
    password: '' // 密码默认为空，只有填了才提交修改
  }
  showEditModal.value = true
}

const saveProfile = async () => {
  if (!currentUser.value?.id) return
  savingProfile.value = true
  try {
    const payload = { ...editForm.value }
    // 如果没有输入密码，则不提交密码修改
    if (!payload.password) {
      delete payload.password
    }

    const res = await axios.put(withApiBase(`/users/${currentUser.value.id}`), payload)
    if (res.data?.code === 200) {
      profile.value = { ...profile.value, ...res.data.data }
      currentUser.value = { ...currentUser.value, ...res.data.data }
      localStorage.setItem('currentUser', JSON.stringify(currentUser.value))
      showEditModal.value = false
    } else {
      alert('保存失败：' + (res.data?.message || '未知错误'))
    }
  } catch (error) {
    console.error(error)
    alert('保存失败，请稍后重试。')
  } finally {
    savingProfile.value = false
  }
}

const handlePublishClickFromNav = () => {
  handlePublishClick({ openLoginModal: () => router.push('/') })
}

const goToNewsDetail = (id) => {
  router.push(`/news/${id}`)
}

const isHistoryUnavailable = (item) => Boolean(item?.is_removed)

const goToEditNews = (id) => {
  router.push(`/publish?edit=${id}`)
}

const auditStatusText = (status) => {
  if (status === 'approved') return '已通过'
  if (status === 'rejected') return '未通过'
  if (status === 'pending') return '待审核'
  if (status === 'draft') return '草稿'
  return status || '待审核'
}

const showToast = (message) => {
  toastMessage.value = message
  toastVisible.value = true
  if (toastTimer) {
    clearTimeout(toastTimer)
  }
  toastTimer = setTimeout(() => {
    toastVisible.value = false
    toastMessage.value = ''
    toastTimer = null
  }, 2200)
}

const isWorksMenuOpen = (newsId) => openedWorksMenuNewsId.value === newsId

const toggleWorksMenu = (newsId) => {
  openedWorksMenuNewsId.value = isWorksMenuOpen(newsId) ? null : newsId
}

const closeWorksMenu = () => {
  openedWorksMenuNewsId.value = null
}

const editWork = (newsId) => {
  closeWorksMenu()
  goToEditNews(newsId)
}

const deleteWork = async (newsId) => {
  if (deletingNewsId.value) return
  if (!window.confirm('确定要删除这篇新闻吗？删除后不可恢复。')) {
    return
  }

  try {
    deletingNewsId.value = newsId
    const res = await axios.delete(`${API_BASE}/news/${newsId}`)
    if (res.data?.code === 200) {
      works.value = works.value.filter((item) => item.id !== newsId)
      closeWorksMenu()
      showToast('删除成功')
      return
    }
    alert(res.data?.message || '删除失败，请稍后重试。')
  } catch (error) {
    console.error(error)
    alert(error?.response?.data?.message || error?.response?.data?.detail || '删除失败，请稍后重试。')
  } finally {
    deletingNewsId.value = null
  }
}

const handleGlobalClick = (event) => {
  const target = event.target
  if (!(target instanceof HTMLElement)) return
  if (!target.closest('.works-menu-wrapper')) {
    closeWorksMenu()
  }
}

const formatViewTime = (value) => {
  if (!value) return ''
  const date = typeof value === 'number'
    ? new Date(value > 1e12 ? value : value * 1000)
    : new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

const normalizeImageUrl = (url) => {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  if (url.startsWith('/')) return `${API_BASE}${url}`
  return `${API_BASE}/${url}`
}

const fetchProfile = async () => {
  if (!currentUser.value?.id) return

  try {
    loadingProfile.value = true
    message.value = ''
    const res = await axios.get(withApiBase(`/users/${currentUser.value.id}`))
    if (res.data?.code === 200) {
      profile.value = res.data.data
      currentUser.value = res.data.data
      localStorage.setItem('currentUser', JSON.stringify(res.data.data))
    }
  } catch (error) {
    console.error(error)
    message.value = '拉取用户信息失败，请稍后重试。'
  } finally {
    loadingProfile.value = false
  }
}

const fetchWorks = async () => {
  try {
    loadingWorks.value = true
    const res = await axios.get(withApiBase('/news/mine?page=1&size=100'))
    if (res.data?.code === 200) {
      works.value = res.data?.data?.items || []
    }
  } catch (error) {
    console.error(error)
    message.value = '拉取作品列表失败。'
  } finally {
    loadingWorks.value = false
  }
}

const fetchFavorites = async () => {
  if (!currentUser.value?.id) return

  loadingFavorites.value = true
  try {
    const res = await axios.get(withApiBase('/favorites/?page=1&size=50'))
    if (res.data?.code !== 200) {
      favorites.value = []
      return
    }

    const items = res.data?.data?.items || []
    if (!items.length) {
      favorites.value = []
      return
    }

    const detailRequests = items.map((fav) =>
      axios
        .get(withApiBase(`/news/detail/${fav.news_id}`))
        .then((detailRes) => {
          const detail = detailRes.data?.data
          if (!detail) return null
          return {
            ...detail,
            favorite_id: fav.id,
            favorite_time: fav.created_at,
          }
        })
        .catch(() => null)
    )

    const detailResults = await Promise.all(detailRequests)
    favorites.value = detailResults.filter(Boolean)
  } catch (error) {
    console.error(error)
    message.value = '拉取收藏列表失败。'
    favorites.value = []
  } finally {
    loadingFavorites.value = false
  }
}

const fetchHistories = async () => {
  if (!currentUser.value?.id) return

  loadingHistories.value = true
  try {
    const res = await axios.get(withApiBase('/history/?page=1&size=50'))
    if (res.data?.code !== 200) {
      histories.value = []
      return
    }

    const items = res.data?.data?.items || []
    if (!items.length) {
      histories.value = []
      return
    }

    histories.value = items.map((h) => ({
      id: h.news_id,
      history_id: h.id,
      title: h.title,
      description: h.description,
      category_name: h.category_name,
      views: h.views,
      image: h.image,
      view_time: h.view_time,
      is_removed: Boolean(h.is_removed),
    }))
  } catch (error) {
    console.error(error)
    message.value = '拉取浏览记录失败。'
    histories.value = []
  } finally {
    loadingHistories.value = false
  }
}

const toggleFavoriteSelectMode = () => {
  favoriteSelectMode.value = !favoriteSelectMode.value
  if (favoriteSelectMode.value) {
    historySelectMode.value = false
    selectedHistoryNewsIds.value = []
  }
  if (!favoriteSelectMode.value) {
    selectedFavoriteNewsIds.value = []
  }
}

const isFavoriteSelected = (newsId) => selectedFavoriteNewsIds.value.includes(newsId)

const toggleFavoriteSelection = (newsId) => {
  if (!favoriteSelectMode.value) return
  if (isFavoriteSelected(newsId)) {
    selectedFavoriteNewsIds.value = selectedFavoriteNewsIds.value.filter((id) => id !== newsId)
    return
  }
  selectedFavoriteNewsIds.value.push(newsId)
}

const handleFavoriteCardClick = (newsId) => {
  if (favoriteSelectMode.value) {
    toggleFavoriteSelection(newsId)
    return
  }
  goToNewsDetail(newsId)
}

const selectAllFavorites = () => {
  selectedFavoriteNewsIds.value = favorites.value.map((item) => item.id)
}

const clearFavoriteSelection = () => {
  selectedFavoriteNewsIds.value = []
}

const toggleHistorySelectMode = () => {
  historySelectMode.value = !historySelectMode.value
  if (historySelectMode.value) {
    favoriteSelectMode.value = false
    selectedFavoriteNewsIds.value = []
  }
  if (!historySelectMode.value) {
    selectedHistoryNewsIds.value = []
  }
}

const isHistorySelected = (newsId) => selectedHistoryNewsIds.value.includes(newsId)

const toggleHistorySelection = (newsId) => {
  if (!historySelectMode.value) return
  if (isHistorySelected(newsId)) {
    selectedHistoryNewsIds.value = selectedHistoryNewsIds.value.filter((id) => id !== newsId)
    return
  }
  selectedHistoryNewsIds.value.push(newsId)
}

const handleHistoryCardClick = (item) => {
  if (historySelectMode.value) {
    toggleHistorySelection(item.id)
    return
  }
  if (isHistoryUnavailable(item)) {
    showToast('新闻已下架，暂不可查看详情。')
    return
  }
  goToNewsDetail(item.id)
}

const selectAllHistories = () => {
  selectedHistoryNewsIds.value = histories.value.map((item) => item.id)
}

const clearHistorySelection = () => {
  selectedHistoryNewsIds.value = []
}

const batchRemoveHistories = async () => {
  if (selectedHistoryNewsIds.value.length === 0) {
    alert('请先勾选要删除的浏览记录。')
    return
  }

  const confirmText = `确定要删除已勾选的 ${selectedHistoryNewsIds.value.length} 条浏览记录吗？`
  if (!window.confirm(confirmText)) {
    return
  }

  try {
    const targets = [...selectedHistoryNewsIds.value]
    const tasks = targets.map((newsId) => axios.delete(withApiBase(`/history/${newsId}`)))
    const results = await Promise.allSettled(tasks)

    const successIds = results
      .map((result, idx) => (result.status === 'fulfilled' && result.value?.data?.code === 200 ? targets[idx] : null))
      .filter(Boolean)

    if (successIds.length > 0) {
      histories.value = histories.value.filter((item) => !successIds.includes(item.id))
      selectedHistoryNewsIds.value = selectedHistoryNewsIds.value.filter((id) => !successIds.includes(id))
    }

    if (successIds.length !== targets.length) {
      alert(`已删除浏览记录 ${successIds.length} 条，${targets.length - successIds.length} 条操作失败。`)
    }
  } catch (error) {
    console.error(error)
    alert('批量删除浏览记录失败，请稍后重试。')
  }
}

const batchRemoveFavorites = async () => {
  if (selectedFavoriteNewsIds.value.length === 0) {
    alert('请先勾选要取消收藏的内容。')
    return
  }

  const confirmText = `确定要取消收藏已勾选的 ${selectedFavoriteNewsIds.value.length} 条内容吗？`
  if (!window.confirm(confirmText)) {
    return
  }

  try {
    const targets = [...selectedFavoriteNewsIds.value]
    const tasks = targets.map((newsId) => axios.delete(withApiBase(`/favorites/${newsId}`)))
    const results = await Promise.allSettled(tasks)

    const successIds = results
      .map((result, idx) => (result.status === 'fulfilled' && result.value?.data?.code === 200 ? targets[idx] : null))
      .filter(Boolean)

    if (successIds.length > 0) {
      favorites.value = favorites.value.filter((item) => !successIds.includes(item.id))
      selectedFavoriteNewsIds.value = selectedFavoriteNewsIds.value.filter((id) => !successIds.includes(id))
    }

    if (successIds.length !== targets.length) {
      alert(`已取消收藏 ${successIds.length} 条，${targets.length - successIds.length} 条操作失败。`)
    }
  } catch (error) {
    console.error(error)
    alert('批量取消收藏失败，请稍后重试。')
  }
}

onMounted(async () => {
  window.addEventListener('click', handleGlobalClick)
  restoreCurrentUser()
  if (!ensureAuthenticated('')) {
    return
  }

  await fetchProfile()
  await fetchWorks()
  await fetchFavorites()
  await fetchHistories()
})

onBeforeUnmount(() => {
  window.removeEventListener('click', handleGlobalClick)
  if (toastTimer) {
    clearTimeout(toastTimer)
    toastTimer = null
  }
})
</script>

<template>
  <div class="profile-layout">
    <TopNavBar
      :current-user="currentUser"
      @logo-click="goHome"
      @profile-click="goToProfile"
      @logout-click="logout"
      @publish-click="handlePublishClickFromNav"
      @login-click="goHome"
    />

    <main class="profile-main">
      <section class="profile-hero" v-if="!loadingProfile">
        <div class="hero-mask"></div>
        <div class="hero-content">
          <!-- settings icon -->
          <div class="settings-btn" @click="openEditModal" title="编辑资料">
            <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="3"></circle>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z">
              </path>
            </svg>
          </div>
          <div class="avatar">{{ avatarText }}</div>
          <div class="user-meta">
            <h1 class="name">{{ displayName }}</h1>
            <p class="username">@{{ profile.username || 'anonymous' }}</p>
            <p class="bio">{{ profileBio }}</p>
          </div>

          <button
            v-if="canAccessBackOffice"
            class="admin-manage-btn"
            type="button"
            @click="goToAdminUserManage"
          >
            后台管理
          </button>
        </div>
      </section>

      <section class="profile-hero loading-hero" v-else>
        正在加载个人信息...
      </section>

      <section class="tab-section">
        <div class="tab-nav">
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'works' }"
            @click="activeTab = 'works'"
          >
            作品 {{ works.length }}
          </button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'favorites' }"
            @click="activeTab = 'favorites'"
          >
            收藏 {{ favorites.length }}
          </button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'histories' }"
            @click="activeTab = 'histories'"
          >
            浏览记录 {{ histories.length }}
          </button>

          <div v-if="activeTab === 'favorites' || activeTab === 'histories'" class="favorite-actions">
            <template v-if="activeTab === 'favorites'">
              <button
                class="batch-btn icon-btn"
                :title="favoriteSelectMode ? '退出勾选模式' : '进入勾选模式'"
                :aria-label="favoriteSelectMode ? '退出勾选模式' : '进入勾选模式'"
                @click="toggleFavoriteSelectMode"
              >
                {{ favoriteSelectMode ? '✕' : '✓' }}
              </button>
              <template v-if="favoriteSelectMode">
                <span class="selected-count">已选 {{ selectedFavoriteNewsIds.length }} 条</span>
                <button
                  class="batch-btn danger"
                  :disabled="selectedFavoriteNewsIds.length === 0"
                  @click="batchRemoveFavorites"
                >
                  取消收藏
                </button>
                <button
                  class="batch-btn"
                  :disabled="favorites.length === 0"
                  @click="selectAllFavorites"
                >
                  全选
                </button>
                <button
                  class="batch-btn"
                  :disabled="selectedFavoriteNewsIds.length === 0"
                  @click="clearFavoriteSelection"
                >
                  取消全选
                </button>
              </template>
            </template>

            <template v-else>
              <button
                class="batch-btn icon-btn"
                :title="historySelectMode ? '退出勾选模式' : '进入勾选模式'"
                :aria-label="historySelectMode ? '退出勾选模式' : '进入勾选模式'"
                @click="toggleHistorySelectMode"
              >
                {{ historySelectMode ? '✕' : '✓' }}
              </button>
              <template v-if="historySelectMode">
                <span class="selected-count">已选 {{ selectedHistoryNewsIds.length }} 条</span>
                <button
                  class="batch-btn danger"
                  :disabled="selectedHistoryNewsIds.length === 0"
                  @click="batchRemoveHistories"
                >
                  删除记录
                </button>
                <button
                  class="batch-btn"
                  :disabled="histories.length === 0"
                  @click="selectAllHistories"
                >
                  全选
                </button>
                <button
                  class="batch-btn"
                  :disabled="selectedHistoryNewsIds.length === 0"
                  @click="clearHistorySelection"
                >
                  取消全选
                </button>
              </template>
            </template>
          </div>
        </div>

        <div v-if="message" class="tip error">{{ message }}</div>

        <div v-if="activeTab === 'works'" class="tab-panel">
          <div v-if="loadingWorks" class="tip">正在加载作品...</div>
          <div v-else-if="works.length === 0" class="tip">暂无作品，快去发布第一篇内容吧。</div>
          <div v-else class="news-list">
            <article
              class="news-item"
              v-for="item in works"
              :key="item.id"
              @click="goToNewsDetail(item.id)"
            >
              <div class="news-main">
                <h3 class="title">{{ item.title }}</h3>
                <p class="desc">{{ item.description }}</p>
                <div class="meta">
                  <span>{{ item.category_name }}</span>
                  <span>{{ item.views }} 阅读</span>
                  <span class="audit-badge" :class="item.audit_status">{{ auditStatusText(item.audit_status) }}</span>
                </div>
                <p v-if="item.audit_status === 'rejected'" class="audit-result">审核结果：{{ item.audit_remark || '内容不符合发布要求，请修改后重试。' }}</p>
              </div>
              <img v-if="item.image" :src="normalizeImageUrl(item.image)" alt="cover" class="cover" />
              <div class="works-menu-wrapper" @click.stop>
                <button class="works-menu-trigger" @click="toggleWorksMenu(item.id)">...</button>
                <div v-if="isWorksMenuOpen(item.id)" class="works-menu-dropdown">
                  <button class="works-menu-item" @click="editWork(item.id)">编辑</button>
                  <button class="works-menu-item danger" :disabled="deletingNewsId === item.id" @click="deleteWork(item.id)">
                    {{ deletingNewsId === item.id ? '删除中...' : '删除' }}
                  </button>
                </div>
              </div>
            </article>
          </div>
        </div>

        <div v-else-if="activeTab === 'favorites'" class="tab-panel">
          <div v-if="loadingFavorites" class="tip">正在加载收藏...</div>
          <div v-else-if="favorites.length === 0" class="tip">你还没有收藏内容，去发现页看看吧。</div>
          <div v-else class="news-list">
            <article
              class="news-item"
              :class="{ selected: favoriteSelectMode && isFavoriteSelected(item.id) }"
              v-for="item in favorites"
              :key="item.favorite_id || item.id"
              @click="handleFavoriteCardClick(item.id)"
            >
              <label
                v-if="favoriteSelectMode"
                class="favorite-check"
                @click.stop
              >
                <input
                  type="checkbox"
                  :checked="isFavoriteSelected(item.id)"
                  @change="toggleFavoriteSelection(item.id)"
                />
              </label>
              <div class="news-main">
                <h3 class="title">{{ item.title }}</h3>
                <p class="desc">{{ item.description || (item.content ? item.content.slice(0, 90) + '...' : '') }}</p>
                <div class="meta">
                  <span>{{ item.category_name || '未分类' }}</span>
                  <span>{{ item.views }} 阅读</span>
                  <span v-if="item.favorite_time">收藏于 {{ formatViewTime(item.favorite_time) }}</span>
                </div>
              </div>
              <img v-if="item.image" :src="normalizeImageUrl(item.image)" alt="cover" class="cover" />
            </article>
          </div>
        </div>
        <div v-else-if="activeTab === 'histories'" class="tab-panel">
          <div v-if="loadingHistories" class="tip">正在加载浏览记录...</div>
          <div v-else-if="histories.length === 0" class="tip">还没有浏览记录，去看看新闻吧。</div>
          <div v-else class="news-list">
            <article
              class="news-item"
              :class="{ selected: historySelectMode && isHistorySelected(item.id), unavailable: !historySelectMode && isHistoryUnavailable(item) }"
              v-for="item in histories"
              :key="item.history_id || item.id"
              @click="handleHistoryCardClick(item)"
            >
              <label
                v-if="historySelectMode"
                class="favorite-check"
                @click.stop
              >
                <input
                  type="checkbox"
                  :checked="isHistorySelected(item.id)"
                  @change="toggleHistorySelection(item.id)"
                />
              </label>
              <div class="news-main">
                <h3 class="title">{{ item.title }}</h3>
                <p class="desc">{{ item.description || (item.content ? item.content.slice(0, 90) + '...' : '') }}</p>
                <div class="meta">
                  <span>{{ item.category_name || '未分类' }}</span>
                  <span v-if="!isHistoryUnavailable(item)">{{ item.views }} 阅读</span>
                  <span v-else class="removed-tag">新闻已下架</span>
                  <span v-if="item.view_time">浏览于 {{ formatViewTime(item.view_time) }}</span>
                </div>
              </div>
              <img v-if="item.image && !isHistoryUnavailable(item)" :src="normalizeImageUrl(item.image)" alt="cover" class="cover" />
            </article>
          </div>
        </div>
      </section>
    </main>

    <!-- Edit Profile Modal -->
    <div class="edit-modal-overlay" v-if="showEditModal" @click.self="showEditModal = false">
      <div class="edit-modal">
        <div class="modal-header">
          <p>🇮🇩</p>
          <h3>编辑个人资料</h3>
          <button class="close-btn" @click="showEditModal = false">&times;</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>昵称</label>
            <input type="text" v-model="editForm.nickname" placeholder="输入轻简可爱的昵称" maxlength="50" />
          </div>
          <div class="form-group">
            <label>个人简介</label>
            <textarea v-model="editForm.bio" placeholder="这家伙很懒，什么都没留下..." maxlength="500"></textarea>
          </div>
          <div class="form-group">
            <label>修改密码</label>
            <input type="password" v-model="editForm.password" placeholder="若不修改密码请留空" maxlength="255" autocomplete="new-password" />
          </div>
        </div>
        <div class="modal-footer">
          <button class="cancel-btn" @click="showEditModal = false" :disabled="savingProfile">取消</button>
          <button class="save-btn" @click="saveProfile" :disabled="savingProfile">
            {{ savingProfile ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <transition name="toast-fade">
      <div v-if="toastVisible" class="toast toast-success">{{ toastMessage }}</div>
    </transition>
  </div>
</template>

<style scoped>
.profile-layout {
  min-height: 100vh;
  background: #f3f5f7;
}

.profile-main {
  width: 1170px;
  margin: 76px auto 0;
  padding: 0 16px 40px;
}

.profile-hero {
  position: relative;
  height: 220px;
  border-radius: 12px;
  background: linear-gradient(120deg, #f04142, #ff7e54);
  overflow: hidden;
  box-shadow: 0 8px 24px rgba(240, 65, 66, 0.2);
}

.loading-hero {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
}

.hero-mask {
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at right top, rgba(255, 255, 255, 0.25), transparent 40%);
}

.hero-content {
  position: relative;
  z-index: 1;
  height: 100%;
  display: flex;
  align-items: center;
  gap: 22px;
  padding: 0 34px;
}

.admin-manage-btn {
  position: absolute;
  right: 22px;
  bottom: 18px;
  border: 1px solid rgba(255, 255, 255, 0.55);
  background: rgba(17, 24, 39, 0.32);
  color: #fff;
  border-radius: 999px;
  padding: 8px 14px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.admin-manage-btn:hover {
  background: rgba(17, 24, 39, 0.5);
  transform: translateY(-1px);
}

.avatar {
  width: 96px;
  height: 96px;
  border-radius: 50%;
  background: #fff;
  color: #f04142;
  font-size: 42px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.15);
}

.user-meta .name {
  margin: 0;
  font-size: 34px;
  color: #fff;
  line-height: 1.2;
  text-align: left;
}
.user-meta .p {
  margin: 0;
  font-size: 34px;
  color: #fff;
  line-height: 1.2;
  text-align: left;
}
.username {
  margin: 8px 0 0;
  font-size: 18px;
  color: rgba(255, 255, 255, 0.9);
  text-align: left;
}

.bio {
  margin: 14px 0 0;
  color: #fff;
  max-width: 700px;
  line-height: 1.6;
  text-align: left;
}

.tab-section {
  margin-top: 14px;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
}

.tab-nav {
  display: flex;
  align-items: center;
  border-bottom: 1px solid #eceff3;
  padding: 0 20px;
}

.favorite-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}

.selected-count {
  font-size: 13px;
  color: #f04142;
  background: #fff0f0;
  border: 1px solid #ffd8d8;
  border-radius: 999px;
  padding: 4px 10px;
}

.batch-btn {
  border: 1px solid #d9dde3;
  background: #fff;
  color: #4b5563;
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.icon-btn {
  min-width: 38px;
  font-size: 16px;
  font-weight: 700;
  padding: 6px 10px;
}

.batch-btn:hover:not(:disabled) {
  border-color: #f04142;
  color: #f04142;
}

.batch-btn.danger {
  border-color: #f2c5c5;
  color: #d93025;
  background: #fff5f5;
}

.batch-btn.danger:hover:not(:disabled) {
  border-color: #e58a8a;
  color: #c21f16;
}

.batch-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.tab-btn {
  height: 52px;
  background: transparent;
  border: none;
  padding: 0 14px;
  font-size: 16px;
  color: #5b636f;
  cursor: pointer;
  border-bottom: 3px solid transparent;
}

.tab-btn.active {
  color: #f04142;
  font-weight: 600;
  border-bottom-color: #f04142;
}

.tab-panel {
  padding: 14px 20px 24px;
}

.tip {
  padding: 22px;
  text-align: center;
  color: #7f8793;
}

.tip.error {
  color: #d93025;
}

.news-list {
  display: flex;
  flex-direction: column;
}

.news-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 4px;
  border-bottom: 1px solid #eef0f3;
  cursor: pointer;
}

.news-item:hover .title {
  color: #f04142;
}

.news-item.selected {
  background: #fff6f6;
  border-left: 3px solid #f04142;
  padding-left: 1px;
}

.news-item.unavailable {
  cursor: not-allowed;
  opacity: 0.72;
}

.news-item.unavailable:hover .title {
  color: #222;
}

.news-main {
  flex: 1;
  min-width: 0;
  text-align: left;
}

.title {
  margin: 0;
  color: #222;
  font-size: 20px;
  line-height: 1.4;
  transition: color 0.2s;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
}

.desc {
  margin: 8px 0 10px;
  color: #666;
  line-height: 1.6;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
}

.meta {
  display: flex;
  gap: 12px;
  font-size: 13px;
  color: #8a8f99;
}

.audit-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  border: 1px solid #e2e8f0;
  padding: 0 8px;
  height: 22px;
  font-size: 12px;
  line-height: 20px;
}

.audit-badge.pending {
  color: #9a3412;
  border-color: #fdba74;
  background: #fff7ed;
}

.audit-badge.approved {
  color: #166534;
  border-color: #86efac;
  background: #f0fdf4;
}

.audit-badge.rejected {
  color: #b91c1c;
  border-color: #fecaca;
  background: #fef2f2;
}

.audit-result {
  margin: 8px 0 0;
  color: #b91c1c;
  font-size: 13px;
  line-height: 1.5;
}

.removed-tag {
  color: #b91c1c;
}

.cover {
  width: 170px;
  height: 106px;
  border-radius: 6px;
  object-fit: cover;
  flex-shrink: 0;
}

.works-menu-wrapper {
  position: relative;
  width: 2.6em;
  min-width: 2.6em;
  flex: 0 0 2.6em;
  display: flex;
  justify-content: flex-end;
  z-index: 5;
}

.works-menu-trigger {
  width: 2.6em;
  min-width: 2.6em;
  height: 28px;
  border: 1px solid #d9dde3;
  border-radius: 8px;
  background: #fff;
  color: #6b7280;
  cursor: pointer;
  line-height: 1;
  font-size: 16px;
}

.works-menu-dropdown {
  position: absolute;
  right: 0;
  top: 34px;
  min-width: 92px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.1);
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.works-menu-item {
  border: none;
  background: #f8fafc;
  border-radius: 6px;
  color: #374151;
  font-size: 13px;
  height: 30px;
  cursor: pointer;
}

.works-menu-item:hover:not(:disabled) {
  background: #eef2ff;
}

.works-menu-item.danger {
  color: #b91c1c;
  background: #fff1f2;
}

.works-menu-item:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.toast {
  position: fixed;
  left: 50%;
  bottom: 72px;
  transform: translateX(-50%);
  z-index: 1000;
  min-width: 140px;
  max-width: 60vw;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 14px;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.16);
}

.toast-success {
  background: #1f9d63;
  color: #fff;
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

.favorite-check {
  display: flex;
  align-items: center;
  justify-content: center;
  padding-right: 8px;
}

.favorite-check input {
  width: 18px;
  height: 18px;
  cursor: pointer;
}

@media (max-width: 1200px) {
  .profile-main {
    width: 100%;
  }
}

@media (max-width: 760px) {
  .hero-content {
    padding: 0 16px;
  }

  .avatar {
    width: 70px;
    height: 70px;
    font-size: 28px;
  }

  .user-meta .name {
    font-size: 26px;
  }

  .news-item {
    flex-direction: column;
  }

  .cover {
    width: 100%;
    height: 180px;
  }

  .favorite-actions {
    margin-left: 8px;
    flex-wrap: wrap;
    justify-content: flex-end;
  }
}

.settings-btn {
  position: absolute;
  top: 20px;
  right: 20px;
  color: #fff;
  cursor: pointer;
  z-index: 2;
  transition: transform 0.3s ease, background 0.3s ease;
  padding: 8px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.1);
}
.settings-btn:hover {
  transform: rotate(90deg);
  background: rgba(255, 255, 255, 0.2);
}

.edit-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.edit-modal {
  width: 420px;
  max-width: 90vw;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: modal-pop 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

@keyframes modal-pop {
  0% { transform: scale(0.9); opacity: 0; }
  100% { transform: scale(1); opacity: 1; }
}

.modal-header {
  text-align: left ;
  display: flex;
  justify-content: space-between;
  align-items: left;
  padding: 18px 24px;
  border-bottom: 1px solid #f0f2f5;
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  color: #222;
  font-weight: 600;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  line-height: 1;
  color: #a0a5ab;
  cursor: pointer;
  padding: 4px;
  transition: color 0.2s;
}
.close-btn:hover {
  color: #333;
}

.modal-body {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.modal-body label {
  text-align: left;
  padding-left: 10px;
  font-size: 16px;
  font-weight: 800;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  font-size: 14px;
  color: #555;
  font-weight: 500;
}

.form-group input,
.form-group textarea {
  width: 100%;
  padding: 12px 14px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  font-size: 14px;
  color: #333;
  background-color: #f7f8fa;
  transition: border-color 0.2s, box-shadow 0.2s, background-color 0.2s;
  box-sizing: border-box;
}

.form-group input:focus,
.form-group textarea:focus {
  outline: none;
  background-color: #ffffff;
  border-color: #f04142;
  box-shadow: 0 0 0 2px rgba(240, 65, 66, 0.1);
}

.form-group textarea {
  resize: vertical;
  min-height: 100px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  background: #fafafa;
  border-top: 1px solid #f0f2f5;
}

.cancel-btn, .save-btn {
  padding: 9px 20px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.cancel-btn {
  border: 1px solid #dcdfe6;
  background: #fff;
  color: #606266;
}

.cancel-btn:hover:not(:disabled) {
  background: #f4f4f5;
  color: #333;
}

.save-btn {
  border: none;
  background: #f04142;
  color: #fff;
  font-weight: 500;
}

.save-btn:hover:not(:disabled) {
  background: #d93025;
}

.save-btn:disabled,
.cancel-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>