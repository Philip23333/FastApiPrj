<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import TopNavBar from '../components/TopNavBar.vue'
import { useTopNavAuth } from '../composables/useTopNavAuth'

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

const displayName = computed(() => profile.value.nickname || profile.value.username || '头条用户')
const avatarText = computed(() => (displayName.value || '头').slice(0, 1).toUpperCase())
const profileBio = computed(() => profile.value.bio || '这个人很低调，还没有写简介。')

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

    const res = await axios.put(`http://127.0.0.1:8080/users/${currentUser.value.id}`, payload)
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

const formatViewTime = (value) => {
  if (!value) return ''
  const date = typeof value === 'number'
    ? new Date(value > 1e12 ? value : value * 1000)
    : new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

const fetchProfile = async () => {
  if (!currentUser.value?.id) return

  try {
    loadingProfile.value = true
    message.value = ''
    const res = await axios.get(`http://127.0.0.1:8080/users/${currentUser.value.id}`)
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
    const res = await axios.get('http://127.0.0.1:8080/news/?page=1&size=100')
    if (res.data?.code === 200) {
      const allNews = res.data?.data?.items || []
      const keywordA = profile.value.nickname || ''
      const keywordB = profile.value.username || ''

      works.value = allNews.filter((item) => {
        const author = item.author || ''
        return (keywordA && author === keywordA) || (keywordB && author === keywordB)
      })
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
    const res = await axios.get('http://127.0.0.1:8080/favorites?page=1&size=50')
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
        .get(`http://127.0.0.1:8080/news/detail/${fav.news_id}`)
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
    const res = await axios.get('http://127.0.0.1:8080/history?page=1&size=50')
    if (res.data?.code !== 200) {
      histories.value = []
      return
    }

    const items = res.data?.data?.items || []
    if (!items.length) {
      histories.value = []
      return
    }

    const detailRequests = items.map((h) =>
      axios
        .get(`http://127.0.0.1:8080/news/detail/${h.news_id}`)
        .then((detailRes) => {
          const detail = detailRes.data?.data
          if (!detail) return null
          return {
            ...detail,
            history_id: h.id,
            view_time: h.view_time,
          }
        })
        .catch(() => null)
    )

    const detailResults = await Promise.all(detailRequests)
    histories.value = detailResults.filter(Boolean)
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

const handleHistoryCardClick = (newsId) => {
  if (historySelectMode.value) {
    toggleHistorySelection(newsId)
    return
  }
  goToNewsDetail(newsId)
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
    const tasks = targets.map((newsId) => axios.delete(`http://127.0.0.1:8080/history/${newsId}`))
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
    const tasks = targets.map((newsId) => axios.delete(`http://127.0.0.1:8080/favorites/${newsId}`))
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
  restoreCurrentUser()
  if (!ensureAuthenticated('')) {
    return
  }

  await fetchProfile()
  await fetchWorks()
  await fetchFavorites()
  await fetchHistories()
})
</script>

<template>
  <div class="profile-layout">
    <TopNavBar
      :current-user="currentUser"
      logo-tag="个人主页"
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
                </div>
              </div>
              <img v-if="item.image" :src="item.image" alt="cover" class="cover" />
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
              <img v-if="item.image" :src="item.image" alt="cover" class="cover" />
            </article>
          </div>
        </div>
        <div v-else-if="activeTab === 'histories'" class="tab-panel">
          <div v-if="loadingHistories" class="tip">正在加载浏览记录...</div>
          <div v-else-if="histories.length === 0" class="tip">还没有浏览记录，去看看新闻吧。</div>
          <div v-else class="news-list">
            <article
              class="news-item"
              :class="{ selected: historySelectMode && isHistorySelected(item.id) }"
              v-for="item in histories"
              :key="item.history_id || item.id"
              @click="handleHistoryCardClick(item.id)"
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
                  <span>{{ item.views }} 阅读</span>
                  <span v-if="item.view_time">浏览于 {{ formatViewTime(item.view_time) }}</span>
                </div>
              </div>
              <img v-if="item.image" :src="item.image" alt="cover" class="cover" />
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

.news-main {
  flex: 1;
  text-align: left;
}

.title {
  margin: 0;
  color: #222;
  font-size: 20px;
  line-height: 1.4;
  transition: color 0.2s;
}

.desc {
  margin: 8px 0 10px;
  color: #666;
  line-height: 1.6;
}

.meta {
  display: flex;
  gap: 12px;
  font-size: 13px;
  color: #8a8f99;
}

.cover {
  width: 170px;
  height: 106px;
  border-radius: 6px;
  object-fit: cover;
  flex-shrink: 0;
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