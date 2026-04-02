<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { withApiBase } from '../config/api'

const props = defineProps({
  currentUser: {
    type: Object,
    default: null,
  },
  logoText: {
    type: String,
    default: '头条',
  },
  logoTag: {
    type: String,
    default: '测试版',
  }
})

const emit = defineEmits(['logo-click', 'login-click', 'profile-click', 'logout-click', 'publish-click'])
const router = useRouter()

const keyword = ref('')
const suggestions = ref([])
const showSuggestions = ref(false)
const searchWrapperRef = ref(null)
let suggestTimer = null

const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const getHighlightParts = (text) => {
  const source = (text || '').toString()
  const key = keyword.value.trim()
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

const handleLogoClick = () => {
  emit('logo-click')
}

const hideSuggestions = () => {
  showSuggestions.value = false
}

const submitSearch = () => {
  const q = keyword.value.trim()
  if (!q) {
    hideSuggestions()
    return
  }
  hideSuggestions()
  router.push({ path: '/search', query: { q } })
}

const handleSuggestionClick = (item) => {
  keyword.value = item.title
  hideSuggestions()
  submitSearch()
}

const onInputFocus = () => {
  if (suggestions.value.length > 0) {
    showSuggestions.value = true
  }
}

const handleDocumentClick = (event) => {
  if (!searchWrapperRef.value) return
  if (!searchWrapperRef.value.contains(event.target)) {
    hideSuggestions()
  }
}

const fetchSuggestions = async () => {
  const q = keyword.value.trim()
  if (!q) {
    suggestions.value = []
    hideSuggestions()
    return
  }

  try {
    const res = await axios.get(withApiBase('/news/search/suggest'), {
      params: { q, limit: 5 }
    })
    if (res.data?.code === 200) {
      suggestions.value = res.data.data || []
      showSuggestions.value = suggestions.value.length > 0
    }
  } catch (error) {
    console.error('搜索建议请求失败:', error)
    suggestions.value = []
    hideSuggestions()
  }
}

watch(keyword, () => {
  if (suggestTimer) {
    clearTimeout(suggestTimer)
  }
  suggestTimer = setTimeout(fetchSuggestions, 220)
})

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
})

onBeforeUnmount(() => {
  if (suggestTimer) {
    clearTimeout(suggestTimer)
  }
  document.removeEventListener('click', handleDocumentClick)
})
</script>

<template>
  <header class="tt-header">
    <div class="header-inner">
      <div class="logo" @click="handleLogoClick">
        {{ logoText }}
        <span>{{ logoTag }}</span>
      </div>
      <div class="search-box" ref="searchWrapperRef">
        <input
          v-model="keyword"
          type="text"
          placeholder="搜一下你感兴趣的资讯..."
          @focus="onInputFocus"
          @keydown.enter.prevent="submitSearch"
        />
        <button class="search-btn" @click="submitSearch">搜索</button>
        <ul v-if="showSuggestions" class="suggestion-list">
          <li
            v-for="item in suggestions"
            :key="item.id"
            class="suggestion-item"
            @click="handleSuggestionClick(item)"
          >
            <span
              v-for="(part, idx) in getHighlightParts(item.title)"
              :key="`sg-${item.id}-${idx}`"
              :class="{ 'highlight-keyword': part.hit }"
            >
              {{ part.text }}
            </span>
          </li>
        </ul>
      </div>
      <div class="user-action">
        <button class="publish-btn" @click="$emit('publish-click')">发布新闻</button>
        <template v-if="props.currentUser">
          <span class="user-name" @click="$emit('profile-click')" title="进入个人中心">
            {{ props.currentUser.nickname || props.currentUser.username }}
          </span>
          <span class="logout-text" @click="$emit('logout-click')">退出</span>
        </template>
        <template v-else>
          <span class="login-text" @click="$emit('login-click')">登录</span>
        </template>
      </div>
    </div>
  </header>
</template>

<style scoped>
.tt-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 60px;
  background-color: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  z-index: 1000;
  display: flex;
  justify-content: center;
}

.header-inner {
  width: 1170px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
}

.logo {
  font-size: 24px;
  font-weight: 800;
  color: #f04142;
  cursor: pointer;
  display: flex;
  align-items: center;
}

.logo span {
  font-size: 12px;
  background: white;
  color: #f04142;
  border: 1px solid #f04142;
  padding: 1px 4px;
  border-radius: 4px;
  margin-left: 8px;
  font-weight: 500;
  transform: translateY(2px);
}

.search-box {
  display: flex;
  width: 400px;
  height: 40px;
  position: relative;
}

.search-box input {
  flex: 1;
  height: 100%;
  border: 1px solid #e8e8e8;
  background-color: #f5f5f5;
  color: #1f2937;
  border-radius: 4px 0 0 4px;
  padding: 0 16px;
  font-size: 15px;
  outline: none;
  transition: all 0.2s;
}

.search-box input::placeholder {
  color: #8b95a1;
}

.search-box input:focus {
  background-color: #fff;
  border-color: #406599;
}

.search-btn {
  width: 80px;
  height: 100%;
  background-color: #2459a2;
  color: #fff;
  border: none;
  border-radius: 0 4px 4px 0;
  font-size: 16px;
  cursor: pointer;
}

.search-btn:hover {
  background-color: #1a427d;
}

.suggestion-list {
  position: absolute;
  top: 44px;
  left: 0;
  right: 0;
  text-align: left;
  margin: 0;
  padding: 6px 0;
  list-style: none;
  background: #fff;
  border: 1px solid #eceff3;
  border-radius: 8px;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.08);
  z-index: 1200;
}

.suggestion-item {
  padding: 10px 12px;
  text-align: left;
  color: #2f3640;
  font-size: 14px;
  line-height: 1.4;
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.suggestion-item:hover {
  background: #f6f8fb;
  color: #f04142;
}

.highlight-keyword {
  color: #d93025;
  font-weight: 700;
}

.user-action {
  display: flex;
  align-items: center;
  gap: 16px;
}

.publish-btn {
  background-color: #f04142;
  color: #fff;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
}

.publish-btn:hover {
  background-color: #d83536;
}

.login-text {
  color: #406599;
  font-size: 15px;
  cursor: pointer;
}

.logout-text {
  font-size: 14px;
  color: #999;
  cursor: pointer;
}

.logout-text:hover {
  color: #f04142;
}

.user-name {
  color: #222;
  font-weight: bold;
  font-size: 15px;
  cursor: pointer;
  transition: color 0.2s;
}

.user-name:hover {
  color: #f04142;
  text-decoration: underline;
}
</style>