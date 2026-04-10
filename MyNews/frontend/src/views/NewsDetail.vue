<script setup>
import { ref, onMounted, onBeforeUnmount, watch, computed, nextTick, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import axios from 'axios'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import emojiData from '@emoji-mart/data'
import { Picker as EmojiMartPicker } from 'emoji-mart'
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
const likeLoading = ref(false)
const isLiked = ref(false)
const likeCount = ref(0)
const comments = ref([])
const commentsLoading = ref(false)
const commentsError = ref('')
const highlightedCommentId = ref(0)
const pendingCommentId = ref(0)
const pendingScrollToComment = ref(false)
const commentSectionRef = ref(null)
const commentInputRef = ref(null)
const showCommentComposer = ref(false)
const showEmojiPicker = ref(false)
const emojiTarget = ref('comment')
const commentEmojiPickerHostRef = ref(null)
const replyEmojiPickerHostRef = ref(null)
const commentSubmitting = ref(false)
const commentDraft = ref('')
const replyDraft = ref('')
const replySubmitting = ref(false)
const activeReplyCommentId = ref(0)
const expandedReplyState = reactive({})
const commentToast = ref('')
let commentToastTimer = null
const emojiPickerData = emojiData
let emojiPickerInstance = null
const showSummaryDrawer = ref(false)
const summaryLoading = ref(false)
const summaryError = ref('')
const summaryContent = ref('')
const summaryModel = ref('')
const summaryTime = ref('')

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
      isLiked.value = !!response.data.data?.is_liked
      likeCount.value = Number(response.data.data?.like_count || 0)
      
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

const fetchComments = async () => {
  if (!newsId.value) return
  commentsLoading.value = true
  commentsError.value = ''
  syncCommentFocusRequestFromRoute()
  try {
    let res = await axios.get(withApiBase(`/comments/news/${newsId.value}?page=1&size=100`))
    if (res.data?.code === 200) {
      comments.value = res.data?.data?.items || []

      // 从个人页带 commentId 跳转时，若首屏评论未命中则扩大查询范围提升命中率。
      if (pendingCommentId.value && !comments.value.some((item) => item.id === pendingCommentId.value)) {
        const largeRes = await axios.get(withApiBase(`/comments/news/${newsId.value}?page=1&size=500`))
        if (largeRes.data?.code === 200) {
          comments.value = largeRes.data?.data?.items || comments.value
        }
      }

      await tryFocusCommentFromRoute()
      return
    }
    comments.value = []
  } catch (err) {
    commentsError.value = err?.response?.data?.message || '评论加载失败，请稍后重试'
    comments.value = []
  } finally {
    commentsLoading.value = false
  }
}

const threadedComments = computed(() => {
  const source = Array.isArray(comments.value) ? comments.value : []
  const rootList = []
  const rootMap = new Map()

  for (const item of source) {
    if (!item || item.parent_comment_id) continue
    rootMap.set(item.id, { ...item, replies: [] })
    rootList.push(rootMap.get(item.id))
  }

  for (const item of source) {
    if (!item || !item.parent_comment_id) continue
    const parent = rootMap.get(item.parent_comment_id)
    if (parent) {
      parent.replies.push(item)
    }
  }

  rootList.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

  for (const root of rootList) {
    root.replies.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  }

  return rootList
})

const getVisibleReplies = (item) => {
  const replies = Array.isArray(item?.replies) ? item.replies : []
  if (replies.length <= 1) return replies
  return expandedReplyState[item.id] ? replies : replies.slice(0, 1)
}

const toggleReplies = (commentId) => {
  expandedReplyState[commentId] = !expandedReplyState[commentId]
}

const openReplyComposer = async (item) => {
  if (!currentUser.value?.id) {
    showAuthModal.value = true
    return
  }

  const targetId = Number(item?.id || 0)
  if (!targetId) return

  if (activeReplyCommentId.value === targetId) {
    activeReplyCommentId.value = 0
    replyDraft.value = ''
    showEmojiPicker.value = false
    return
  }

  activeReplyCommentId.value = targetId
  replyDraft.value = ''
  showEmojiPicker.value = false
  await nextTick()
}

const closeReplyComposer = () => {
  activeReplyCommentId.value = 0
  replyDraft.value = ''
  showEmojiPicker.value = false
}

const toggleEmojiPicker = async (target = 'comment') => {
  if (showEmojiPicker.value && emojiTarget.value === target) {
    showEmojiPicker.value = false
    return
  }

  emojiTarget.value = target
  showEmojiPicker.value = true
  await nextTick()
  mountEmojiPicker()
}

const handleDocumentClick = (event) => {
  const target = event.target
  if (!(target instanceof Element)) return

  const keepOpen = target.closest(
    '.comment-composer, .reply-composer, .emoji-picker, .open-comment-btn, .reply-btn, .emoji-toggle, .reply-emoji-toggle'
  )
  if (keepOpen) return

  showEmojiPicker.value = false
  closeReplyComposer()
}

const syncCommentFocusRequestFromRoute = () => {
  pendingCommentId.value = Number(route.query.commentId || 0)
  pendingScrollToComment.value = route.query.toComment === '1' || !!pendingCommentId.value
}

const tryFocusCommentFromRoute = async () => {
  if (pendingCommentId.value) {
    const pending = comments.value.find((item) => item.id === pendingCommentId.value)
    if (pending?.parent_comment_id) {
      expandedReplyState[pending.parent_comment_id] = true
    }
  }

  await nextTick()

  if (pendingCommentId.value) {
    const target = document.getElementById(`comment-${pendingCommentId.value}`)
    if (target) {
      const focusedId = pendingCommentId.value
      highlightedCommentId.value = focusedId
      target.scrollIntoView({ behavior: 'smooth', block: 'center' })
      pendingCommentId.value = 0
      pendingScrollToComment.value = false
      setTimeout(() => {
        if (highlightedCommentId.value === focusedId) {
          highlightedCommentId.value = 0
        }
      }, 2200)
      return
    }
  }

  if (pendingScrollToComment.value && commentSectionRef.value) {
    scrollToCommentSection()
    pendingScrollToComment.value = false
  }
}

const scrollToCommentSection = () => {
  if (!commentSectionRef.value) return
  commentSectionRef.value.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const openCommentComposer = async () => {
  if (!currentUser.value?.id) {
    showAuthModal.value = true
    return
  }
  showCommentComposer.value = true
  showEmojiPicker.value = false
  emojiTarget.value = 'comment'
  await nextTick()
  commentInputRef.value?.focus()
  scrollToCommentSection()
}

const appendEmoji = (emoji) => {
  const text = typeof emoji === 'string' ? emoji : (emoji?.native || '')
  if (!text) return

  if (emojiTarget.value === 'reply' && activeReplyCommentId.value) {
    replyDraft.value += text
    return
  }

  commentDraft.value += text
  commentInputRef.value?.focus()
}

const resolveHostElement = (hostRefValue) => {
  if (Array.isArray(hostRefValue)) {
    return hostRefValue[0] || null
  }
  return hostRefValue || null
}

const mountEmojiPicker = () => {
  const hostRaw = emojiTarget.value === 'reply' ? replyEmojiPickerHostRef.value : commentEmojiPickerHostRef.value
  const host = resolveHostElement(hostRaw)
  if (!host) return
  host.innerHTML = ''
  emojiPickerInstance = new EmojiMartPicker({
    data: emojiPickerData,
    theme: 'light',
    previewPosition: 'none',
    skinTonePosition: 'search',
    perLine: 9,
    maxFrequentRows: 2,
    onEmojiSelect: appendEmoji,
  })
  host.appendChild(emojiPickerInstance)
}

const showCommentToast = (message) => {
  commentToast.value = message
  if (commentToastTimer) {
    clearTimeout(commentToastTimer)
  }
  commentToastTimer = setTimeout(() => {
    commentToast.value = ''
    commentToastTimer = null
  }, 1800)
}

const submitComment = async () => {
  const content = commentDraft.value.trim()
  if (!content || commentSubmitting.value) return
  if (!currentUser.value?.id) {
    showAuthModal.value = true
    return
  }

  commentSubmitting.value = true
  commentsError.value = ''
  try {
    const res = await axios.post(withApiBase(`/comments/${newsId.value}`), { content })
    if (res.data?.code === 200 && res.data?.data) {
      comments.value = [res.data.data, ...comments.value]
      commentDraft.value = ''
      showEmojiPicker.value = false
      emojiTarget.value = 'comment'
      showCommentToast('评论发布成功')
      if (newsItem.value) {
        newsItem.value.comment_count = Number(newsItem.value.comment_count || 0) + 1
      }
      return
    }
    commentsError.value = '评论发布失败，请稍后重试'
  } catch (err) {
    commentsError.value = err?.response?.data?.message || err?.response?.data?.detail || '评论发布失败，请稍后重试'
  } finally {
    commentSubmitting.value = false
  }
}

const submitReply = async (item) => {
  const parentId = Number(item?.id || 0)
  const content = replyDraft.value.trim()
  if (!parentId || !content || replySubmitting.value) return

  if (!currentUser.value?.id) {
    showAuthModal.value = true
    return
  }

  replySubmitting.value = true
  commentsError.value = ''
  try {
    const res = await axios.post(withApiBase(`/comments/${newsId.value}`), {
      content,
      parent_comment_id: parentId,
    })
    if (res.data?.code === 200 && res.data?.data) {
      comments.value = [res.data.data, ...comments.value]
      expandedReplyState[parentId] = true
      replyDraft.value = ''
      activeReplyCommentId.value = 0
      showEmojiPicker.value = false
      emojiTarget.value = 'comment'
      showCommentToast('回复发布成功')
      if (newsItem.value) {
        newsItem.value.comment_count = Number(newsItem.value.comment_count || 0) + 1
      }
      return
    }
    commentsError.value = '回复发布失败，请稍后重试'
  } catch (err) {
    commentsError.value = err?.response?.data?.message || err?.response?.data?.detail || '回复发布失败，请稍后重试'
  } finally {
    replySubmitting.value = false
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

const toggleLike = async () => {
  if (likeLoading.value) return

  if (!currentUser.value?.id) {
    showAuthModal.value = true
    return
  }

  likeLoading.value = true
  try {
    const request = isLiked.value
      ? axios.delete(withApiBase(`/likes/${newsId.value}`))
      : axios.post(withApiBase(`/likes/${newsId.value}`))
    const res = await request
    if (res.data?.code === 200) {
      isLiked.value = !!res.data?.data?.is_liked
      likeCount.value = Number(res.data?.data?.like_count || 0)
      if (newsItem.value) {
        newsItem.value.like_count = likeCount.value
      }
    }
  } catch (err) {
    alert(err?.response?.data?.message || '点赞操作失败，请稍后重试')
  } finally {
    likeLoading.value = false
  }
}

const renderSummaryMarkdown = (content) => {
  const raw = content || ''
  const parsed = marked.parse(raw, { gfm: true, breaks: true })
  return DOMPurify.sanitize(typeof parsed === 'string' ? parsed : '')
}

const generateSummary = async () => {
  if (summaryLoading.value) return
  summaryError.value = ''
  summaryLoading.value = true
  try {
    const response = await axios.post(withApiBase(`/ai/news/${newsId.value}/chat`), {
      question: '请基于当前新闻内容给出一份结构化全文总结，突出关键信息、背景与影响。',
      temperature: 0.2,
    })
    const data = response?.data?.data || {}
    summaryContent.value = data.answer || 'AI未生成总结内容。'
    summaryModel.value = data.model || ''
    summaryTime.value = new Date().toLocaleTimeString()
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

  if (!summaryContent.value && !summaryLoading.value) {
    await generateSummary()
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
    fetchComments()
    reportViewHistory()
  }
})

watch(
  () => [route.query.commentId, route.query.toComment],
  () => {
    syncCommentFocusRequestFromRoute()
    if (route.params.id === newsId.value) {
      fetchComments()
    }
  }
)

const handlePublishClickFromNav = () => {
  handlePublishClick({ openLoginModal: () => { showAuthModal.value = true } })
}

const formatTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2,'0')}-${date.getDate().toString().padStart(2,'0')} ${date.getHours().toString().padStart(2,'0')}:${date.getMinutes().toString().padStart(2,'0')}`
}

const formatRelativeTime = (dateStr) => {
  if (!dateStr) return ''
  const now = Date.now()
  const t = new Date(dateStr).getTime()
  if (Number.isNaN(t)) return ''
  const diffSec = Math.floor((now - t) / 1000)
  if (diffSec < 60) return '刚刚'
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}分钟前`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour}小时前`
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 7) return `${diffDay}天前`
  return formatTime(dateStr)
}

onMounted(() => {
  syncCommentFocusRequestFromRoute()
  restoreCurrentUser()
  fetchNewsDetail()
  fetchFavoriteStatus()
  fetchComments()
  reportViewHistory()
  document.addEventListener('click', handleDocumentClick)
})

const handleAuthSuccessFromModal = async (payload) => {
  handleAuthSuccess(payload)
  await fetchFavoriteStatus()
  await fetchComments()
  await reportViewHistory()
}

watch(
  () => newsItem.value?.id,
  async () => {
    await tryFocusCommentFromRoute()
  }
)

watch(showEmojiPicker, async (visible) => {
  if (!visible) return
  await nextTick()
  mountEmojiPicker()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
  if (commentToastTimer) {
    clearTimeout(commentToastTimer)
    commentToastTimer = null
  }
  const commentHost = resolveHostElement(commentEmojiPickerHostRef.value)
  const replyHost = resolveHostElement(replyEmojiPickerHostRef.value)
  if (commentHost) commentHost.innerHTML = ''
  if (replyHost) replyHost.innerHTML = ''
  emojiPickerInstance = null
})
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
          <div class="action-btn" :class="{ active: isLiked }" @click="toggleLike">
            <span class="icon">👍</span>
            <span class="text">{{ likeLoading ? '处理中' : `点赞 ${likeCount}` }}</span>
          </div>
          <div
            class="action-btn"
            :class="{ active: isFavorited }"
            @click="toggleFavorite"
          >
            <span class="icon">{{ isFavorited ? '★' : '☆' }}</span>
            <span class="text">{{ favoriteLoading ? '处理中' : (isFavorited ? '已收藏' : '收藏') }}</span>
          </div>
          <div class="action-btn comment-btn" @click="scrollToCommentSection">
            <span class="icon">💬</span>
            <span class="text">评论 {{ newsItem?.comment_count || comments.length || 0 }}</span>
          </div>
          <button v-if="!showSummaryDrawer" class="action-btn summary-btn" type="button" @click="openSummaryDrawer">
            <span class="icon">✨</span>
            <span class="text">一键总结</span>
          </button>
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

          <section ref="commentSectionRef" class="comment-section">
            <div class="comment-head">
              <h3>评论区</h3>
              <div class="comment-head-actions">
                <span>{{ newsItem?.comment_count || comments.length || 0 }} 条评论</span>
                <button class="open-comment-btn" type="button" @click="openCommentComposer">发布评论</button>
              </div>
            </div>

            <div v-if="showCommentComposer" class="comment-composer">
              <textarea
                ref="commentInputRef"
                v-model="commentDraft"
                class="comment-input"
                rows="4"
                maxlength="1000"
                placeholder="写下你的观点，友善交流更有价值..."
              ></textarea>
              <div class="comment-tools">
                <button type="button" class="emoji-toggle" @click="toggleEmojiPicker('comment')">😀 表情</button>
                <button type="button" class="submit-comment-btn" :disabled="commentSubmitting || !commentDraft.trim()" @click="submitComment">
                  {{ commentSubmitting ? '发布中...' : '发布评论' }}
                </button>
              </div>
              <div v-if="showEmojiPicker && emojiTarget === 'comment'" class="emoji-picker">
                <div ref="commentEmojiPickerHostRef"></div>
              </div>
            </div>

            <div v-if="commentsLoading" class="comment-tip">正在加载评论...</div>
            <p v-else-if="commentsError" class="comment-tip error">{{ commentsError }}</p>
            <div v-else-if="comments.length === 0" class="comment-tip">暂无评论，快来抢沙发吧。</div>
            <div v-else class="comment-list">
              <article
                v-for="item in threadedComments"
                :id="`comment-${item.id}`"
                :key="item.id"
                class="comment-item"
                :class="{ focused: highlightedCommentId === item.id }"
              >
                <div class="comment-meta">
                  <span class="author">{{ item.nickname || item.username || '用户' }}</span>
                  <span>{{ formatRelativeTime(item.created_at) }}</span>
                </div>
                <p class="comment-content">{{ item.content }}</p>

                <div class="comment-actions">
                  <button class="reply-btn" type="button" @click="openReplyComposer(item)">回复评论</button>
                </div>

                <div v-if="activeReplyCommentId === item.id" class="reply-composer">
                  <textarea
                    v-model="replyDraft"
                    class="reply-input"
                    rows="3"
                    maxlength="1000"
                    :placeholder="`回复 ${item.nickname || item.username || '用户'}...`"
                  ></textarea>
                  <div class="reply-tools">
                    <button type="button" class="reply-emoji-toggle" @click="toggleEmojiPicker('reply')">😀 表情</button>
                    <button type="button" class="reply-cancel-btn" @click="closeReplyComposer">取消</button>
                    <button
                      type="button"
                      class="reply-submit-btn"
                      :disabled="replySubmitting || !replyDraft.trim()"
                      @click="submitReply(item)"
                    >
                      {{ replySubmitting ? '发布中...' : '发布回复' }}
                    </button>
                  </div>
                  <div v-if="showEmojiPicker && emojiTarget === 'reply'" class="emoji-picker reply-emoji-picker">
                    <div ref="replyEmojiPickerHostRef"></div>
                  </div>
                </div>

                <div v-if="item.replies && item.replies.length" class="reply-list-wrap">
                  <article
                    v-for="reply in getVisibleReplies(item)"
                    :id="`comment-${reply.id}`"
                    :key="reply.id"
                    class="reply-item"
                    :class="{ focused: highlightedCommentId === reply.id }"
                  >
                    <div class="comment-meta">
                      <span class="author">{{ reply.nickname || reply.username || '用户' }}</span>
                      <span>{{ formatRelativeTime(reply.created_at) }}</span>
                    </div>
                    <p class="comment-content">{{ reply.content }}</p>
                  </article>

                  <button
                    v-if="item.replies.length > 1"
                    type="button"
                    class="toggle-replies-btn"
                    @click="toggleReplies(item.id)"
                  >
                    {{ expandedReplyState[item.id] ? '收起回复' : `展开更多回复（${item.replies.length - 1}）` }}
                  </button>
                </div>
              </article>
            </div>
          </section>
          
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

    </main>

    <section v-if="showSummaryDrawer" class="summary-chat-window">
      <section class="summary-drawer">
        <header>
          <div>
            <h3>AI全文总结</h3>
            <p>{{ newsItem?.title || '' }}</p>
          </div>
          <button type="button" class="summary-close" aria-label="收起总结对话" @click="closeSummaryDrawer">×</button>
        </header>

        <div class="summary-body">
          <article v-if="summaryContent" class="summary-chat-item assistant">
            <div class="summary-chat-meta">
              <span>AI助手</span>
              <span>{{ summaryTime }}</span>
              <span v-if="summaryModel" class="summary-chat-model">{{ summaryModel }}</span>
            </div>
            <div class="summary-chat-content" v-html="renderSummaryMarkdown(summaryContent)"></div>
          </article>

          <div v-if="summaryLoading" class="summary-loading">正在生成总结...</div>
          <p v-if="summaryError" class="summary-error">{{ summaryError }}</p>
        </div>
      </section>
    </section>

    <AuthModal
      v-model:visible="showAuthModal"
      @success="handleAuthSuccessFromModal"
    />

    <transition name="comment-toast-fade">
      <div v-if="commentToast" class="comment-toast">{{ commentToast }}</div>
    </transition>
  </div>
</template>

<style scoped>
.detail-layout {
  background-color: #fff;
}

/* 主体布局 */
.detail-main {
  width: min(94vw, 1320px);
  margin: 76px auto 0;
  display: grid;
  grid-template-columns: 120px minmax(0, 50vw) 220px;
  justify-content: center;
  align-items: start;
  column-gap: 22px;
}

/* 1. 左操作面板 */
.left-sidebar {
  width: 120px;
  position: sticky;
  top: 96px;
  align-self: start;
}
.action-panel {
  position: sticky;
  top: 96px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
  padding-left: 20px;
  
}
.action-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  background: linear-gradient(180deg, #ffffff 0%, #f3f6fb 100%);
  border-radius: 16px;
  cursor: pointer;
  color: #334155;
  border: 1px solid #e2e8f0;
  transition: all 0.22s ease;
}
.action-btn:hover {
  transform: translateY(-1px);
  border-color: #f2b3b5;
  background: linear-gradient(180deg, #fff6f6 0%, #ffecec 100%);
  color: #e11d48;
}
.action-btn.active {
  background: linear-gradient(180deg, #ffe8ea 0%, #ffd8dc 100%);
  border-color: #f8a7b2;
  color: #be123c;
}
.action-btn .icon {
  font-size: 22px;
}
.action-btn .text {
  font-size: 11px;
  margin-top: 4px;
  text-align: center;
  line-height: 1.2;
}

.comment-btn {
  margin-top: 6px;
}


/* 2. 文章主体 */
.article-container {
  min-width: 0;
  width: 100%;
  max-width: none;
  padding: 0 8px;
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

.comment-section {
  margin-top: 26px;
  border-top: 1px solid #e8e8e8;
  padding-top: 16px;
}

.comment-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.comment-head h3 {
  margin: 0;
  font-size: 20px;
  color: #1f2937;
}

.comment-head span {
  color: #64748b;
  font-size: 13px;
}

.comment-head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.open-comment-btn {
  border: 1px solid #f6b4bd;
  background: #fff1f3;
  color: #be123c;
  border-radius: 999px;
  height: 30px;
  padding: 0 12px;
  font-size: 13px;
  cursor: pointer;
}

.comment-composer {
  position: relative;
  overflow: visible;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 10px;
  margin-bottom: 12px;
  background: #ffffff;
}

.comment-input {
  width: 100%;
  resize: vertical;
  border: 1px solid #d8e0ea;
  border-radius: 10px;
  padding: 10px;
  font-size: 14px;
  color: #1f2937;
  background: #f8fafc;
}

.comment-input:focus {
  outline: none;
  border-color: #f6a9b3;
  background: #fff;
}

.comment-tools {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.emoji-toggle {
  border: 1px solid #d2dae6;
  background: #f8fafc;
  color: #334155;
  border-radius: 8px;
  height: 30px;
  padding: 0 10px;
  cursor: pointer;
}

.submit-comment-btn {
  border: none;
  background: linear-gradient(90deg, #f43f5e, #e11d48);
  color: #fff;
  border-radius: 9px;
  height: 32px;
  padding: 0 14px;
  cursor: pointer;
}

.submit-comment-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.emoji-picker {
  position: absolute;
  left: 10px;
  top: calc(100% + 8px);
  z-index: 1200;
  margin-top: 0;
  display: block;
}

.emoji-picker :deep(em-emoji-picker) {
  width: min(100%, 360px);
  --rgb-background: 255, 255, 255;
  --rgb-color: 31, 41, 55;
  --rgb-accent: 244, 63, 94;
  --border-radius: 12px;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.15);
}

.comment-tip {
  color: #64748b;
  padding: 10px 0;
}

.comment-tip.error {
  color: #b91c1c;
}

.comment-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.comment-item {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 10px 12px;
  background: #fff;
  transition: all 0.22s ease;
  text-align: left;
}

.comment-item.focused {
  border-color: #f59e0b;
  box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.22);
}

.comment-meta {
  display: flex;
  gap: 8px;
  color: #6b7280;
  font-size: 12px;
  margin-bottom: 6px;
}

.comment-meta .author {
  color: #111827;
  font-weight: 600;
}

.comment-content {
  margin: 0;
  color: #334155;
  line-height: 1.65;
  white-space: pre-wrap;
}

.comment-actions {
  margin-top: 8px;
  display: flex;
  justify-content: flex-end;
}

.reply-btn {
  border: 1px solid #d1dbe8;
  background: #f8fafc;
  color: #334155;
  border-radius: 8px;
  height: 28px;
  padding: 0 10px;
  font-size: 12px;
  cursor: pointer;
}

.reply-btn:hover {
  border-color: #f6b4bd;
  background: #fff1f3;
  color: #be123c;
}

.reply-composer {
  position: relative;
  overflow: visible;
  margin-top: 10px;
  padding: 10px;
  border: 1px dashed #d1dbe8;
  border-radius: 10px;
  background: #f8fafc;
}

.reply-input {
  width: 100%;
  resize: vertical;
  border: 1px solid #d8e0ea;
  border-radius: 10px;
  padding: 10px;
  font-size: 14px;
  color: #1f2937;
  background: #ffffff;
}

.reply-input:focus {
  outline: none;
  border-color: #f6a9b3;
}

.reply-tools {
  margin-top: 8px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.reply-emoji-toggle {
  border: 1px solid #d2dae6;
  background: #f8fafc;
  color: #334155;
  border-radius: 8px;
  height: 30px;
  padding: 0 10px;
  cursor: pointer;
}

.reply-emoji-toggle:hover {
  border-color: #f6b4bd;
  background: #fff1f3;
  color: #be123c;
}

.reply-emoji-picker {
  left: 0;
  top: calc(100% + 8px);
}

.reply-cancel-btn {
  border: 1px solid #d1dbe8;
  background: #ffffff;
  color: #334155;
  border-radius: 8px;
  height: 30px;
  padding: 0 10px;
  cursor: pointer;
}

.reply-submit-btn {
  border: none;
  background: linear-gradient(90deg, #f43f5e, #e11d48);
  color: #fff;
  border-radius: 8px;
  height: 30px;
  padding: 0 12px;
  cursor: pointer;
}

.reply-submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.reply-list-wrap {
  margin-top: 10px;
  border-left: 2px solid #e2e8f0;
  padding-left: 10px;
}

.reply-item {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 8px 10px;
  background: #f9fbff;
}

.reply-item + .reply-item {
  margin-top: 8px;
}

.reply-item.focused {
  border-color: #f59e0b;
  box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.22);
}

.toggle-replies-btn {
  margin-top: 8px;
  border: 1px solid #d1dbe8;
  background: #ffffff;
  color: #334155;
  border-radius: 8px;
  height: 28px;
  padding: 0 10px;
  font-size: 12px;
  cursor: pointer;
}

.toggle-replies-btn:hover {
  border-color: #f6b4bd;
  background: #fff1f3;
  color: #be123c;
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
  width:100%;
  position: sticky;
  top: 60px;
  align-self: start;
  text-align: left;
}
.author-card {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 14px;
  margin-bottom: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: static;
  width: 300px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
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
  font-size: 18px;
  font-weight: bold;
  color: #222;
}
.name-box .desc {
  font-size: 13px;
  color: #999;
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

.comment-toast {
  position: fixed;
  left: 50%;
  bottom: 84px;
  transform: translateX(-50%);
  z-index: 1600;
  background: rgba(17, 24, 39, 0.92);
  color: #fff;
  border-radius: 999px;
  padding: 10px 16px;
  font-size: 13px;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.28);
}

.comment-toast-fade-enter-active,
.comment-toast-fade-leave-active {
  transition: opacity 0.24s ease, transform 0.24s ease;
}

.comment-toast-fade-enter-from,
.comment-toast-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}

@media (max-width: 1240px) {
  .detail-main {
    width: min(96vw, 980px);
    grid-template-columns: 92px minmax(0, 1fr) 200px;
    column-gap: 12px;
  }

  .action-btn {
    width: 56px;
    height: 56px;
  }

  .summary-btn {
    margin-top: 120px;
  }
}

@media (max-width: 900px) {
  .detail-main {
    display: block;
    width: 100%;
    padding: 0 10px;
  }

  .left-sidebar,
  .right-sidebar {
    display: none;
  }

  .summary-chat-window {
    right: 8px;
    left: 8px;
    width: auto;
    top: 148px;
    height: 66vh;
  }
}
</style>