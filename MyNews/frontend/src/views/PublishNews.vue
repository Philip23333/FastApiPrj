<script setup>
import { onMounted, onBeforeUnmount, ref, nextTick, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import Quill from 'quill'
import 'quill/dist/quill.snow.css'
import TopNavBar from '../components/TopNavBar.vue'
import { useTopNavAuth } from '../composables/useTopNavAuth'
import { API_BASE_URL } from '../config/api'

const router = useRouter()
const route = useRoute()
const API_BASE = API_BASE_URL

const {
  currentUser,
  restoreCurrentUser,
  logout,
  goHome,
  goToProfile,
  handlePublishClick,
  ensureAuthenticated,
} = useTopNavAuth()

const categories = ref([])
const loadingCategories = ref(false)
const submitting = ref(false)
const submitError = ref('')
const submitSuccess = ref('')
const toastMessage = ref('')
const toastVisible = ref(false)
let toastTimer = null
const loadingEditData = ref(false)
const initialEditFingerprint = ref(null)
const hasEditChanges = ref(false)
const assistantPrompt = ref('')
const assistantLoading = ref(false)
const assistantError = ref('')
const assistantResult = ref(null)

const editNewsId = ref(Number(route.query.edit || 0))
const isEditMode = ref(editNewsId.value > 0)

const form = ref({
  title: '',
  categoryId: '',
  description: '',
  image: '',
})
const coverUploading = ref(false)

const editorRef = ref(null)
let quill = null

const getToken = () => localStorage.getItem('accessToken') || ''

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

const authHeaders = () => {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

const stripHtml = (html) => {
  if (!html) return ''
  const parser = new DOMParser()
  const doc = parser.parseFromString(html, 'text/html')
  return (doc.body.textContent || '').trim()
}

const normalizeHtml = (html) => {
  if (!html) return ''
  const parser = new DOMParser()
  const doc = parser.parseFromString(html, 'text/html')
  return (doc.body.innerHTML || '').trim()
}

const autoFillDescription = () => {
  if (form.value.description.trim()) return
  const plain = stripHtml(quill?.root?.innerHTML || '')
  if (plain) {
    form.value.description = plain.slice(0, 100)
  }
}

const toAbsoluteUrl = (url) => {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  if (url.startsWith('/')) return `${API_BASE}${url}`
  return url
}

const buildSubmitPayload = () => {
  const title = form.value.title.trim()
  const categoryId = Number(form.value.categoryId)
  const category = categories.value.find((c) => c.id === categoryId)
  const html = quill?.root?.innerHTML || ''
  const normalizedHtml = normalizeHtml(html)
  const plain = stripHtml(html)
  const description = form.value.description.trim() || plain.slice(0, 100)
  const image = form.value.image.trim() || null

  return {
    title,
    category,
    html,
    normalizedHtml,
    plain,
    payload: {
      title,
      category_id: category?.id,
      category_name: category?.name,
      content: html,
      description,
      image,
      author: currentUser.value?.username || null,
    },
  }
}

const buildFingerprintFromPayload = (prepared) => {
  return JSON.stringify({
    title: prepared.payload.title,
    category_id: prepared.payload.category_id,
    category_name: prepared.payload.category_name,
    content: prepared.normalizedHtml,
    description: prepared.payload.description,
    image: prepared.payload.image,
  })
}

const updateEditDirtyState = () => {
  if (!isEditMode.value) {
    hasEditChanges.value = true
    return
  }
  if (!initialEditFingerprint.value) {
    hasEditChanges.value = false
    return
  }
  const prepared = buildSubmitPayload()
  const currentFingerprint = buildFingerprintFromPayload(prepared)
  hasEditChanges.value = currentFingerprint !== initialEditFingerprint.value
}

const canSubmit = computed(() => {
  if (submitting.value || loadingEditData.value) return false
  if (!isEditMode.value) return true
  return hasEditChanges.value
})

const fetchCategories = async () => {
  loadingCategories.value = true
  try {
    const res = await axios.get(`${API_BASE}/news/categories`)
    if (res.data?.code === 200) {
      categories.value = res.data.data || []
      if (!form.value.categoryId && categories.value.length > 0) {
        const headline = categories.value.find((cat) => String(cat.name).trim() === '头条')
        form.value.categoryId = String((headline || categories.value[0]).id)
      }
    }
  } catch (e) {
    submitError.value = '分类加载失败，请刷新重试'
  } finally {
    loadingCategories.value = false
  }
}

const loadEditNews = async () => {
  if (!isEditMode.value || !editNewsId.value) return
  loadingEditData.value = true
  try {
    const res = await axios.get(`${API_BASE}/news/editable/${editNewsId.value}`, {
      headers: {
        ...authHeaders(),
      },
    })
    if (res.data?.code !== 200) {
      throw new Error(res.data?.message || '加载待编辑新闻失败')
    }

    const data = res.data.data || {}
    form.value.title = data.title || ''
    form.value.description = data.description || ''
    form.value.image = data.image || ''
    if (data.category_id) {
      form.value.categoryId = String(data.category_id)
    }
    if (quill) {
      quill.root.innerHTML = data.content || ''
    }
    const prepared = buildSubmitPayload()
    initialEditFingerprint.value = buildFingerprintFromPayload(prepared)
  } catch (err) {
    submitError.value = err.response?.data?.message || err.response?.data?.detail || err.message || '加载待编辑新闻失败'
  } finally {
    updateEditDirtyState()
    loadingEditData.value = false
  }
}

const uploadImageAndInsert = async () => {
  const input = document.createElement('input')
  input.setAttribute('type', 'file')
  input.setAttribute('accept', 'image/*')
  input.click()

  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file || !quill) return

    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await axios.post(`${API_BASE}/files/upload`, fd, {
        headers: {
          ...authHeaders(),
          'Content-Type': 'multipart/form-data',
        },
      })

      if (res.data?.code !== 200) {
        throw new Error(res.data?.message || '图片上传失败')
      }

      const rawUrl = res.data?.data?.url || ''
      if (!rawUrl) {
        throw new Error('服务器未返回图片地址')
      }

      const imageUrl = rawUrl.startsWith('http')
        ? rawUrl
        : `${API_BASE}${rawUrl.startsWith('/') ? '' : '/'}${rawUrl}`
      const range = quill.getSelection(true)
      const insertIndex = range ? range.index : quill.getLength()
      quill.insertEmbed(insertIndex, 'image', imageUrl, 'user')
      quill.setSelection(insertIndex + 1, 0)
    } catch (err) {
      submitError.value = err.response?.data?.message || err.message || '图片上传失败'
    }
  }
}

const uploadCoverImage = async () => {
  const input = document.createElement('input')
  input.setAttribute('type', 'file')
  input.setAttribute('accept', 'image/*')
  input.click()

  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file) return

    try {
      coverUploading.value = true
      const fd = new FormData()
      fd.append('file', file)
      const res = await axios.post(`${API_BASE}/files/upload`, fd, {
        headers: {
          ...authHeaders(),
          'Content-Type': 'multipart/form-data',
        },
      })

      if (res.data?.code !== 200) {
        throw new Error(res.data?.message || '封面上传失败')
      }

      const rawUrl = res.data?.data?.url || ''
      if (!rawUrl) {
        throw new Error('服务器未返回封面地址')
      }

      form.value.image = rawUrl
    } catch (err) {
      submitError.value = err.response?.data?.message || err.message || '封面上传失败'
    } finally {
      coverUploading.value = false
    }
  }
}

const initEditor = async () => {
  await nextTick()
  if (!editorRef.value || quill) return

  quill = new Quill(editorRef.value, {
    theme: 'snow',
    placeholder: '请输入新闻正文，支持图文混排...',
    modules: {
      toolbar: {
        container: [
          [{ header: [1, 2, 3, false] }],
          ['bold', 'italic', 'underline', 'strike'],
          [{ color: [] }, { background: [] }],
          [{ list: 'ordered' }, { list: 'bullet' }],
          [{ align: [] }],
          ['link', 'image', 'blockquote', 'code-block'],
          ['clean'],
        ],
        handlers: {
          image: uploadImageAndInsert,
        },
      },
    },
  })

  quill.on('text-change', () => {
    updateEditDirtyState()
  })

  const toolbarModule = quill.getModule('toolbar')
  const toolbarEl = toolbarModule?.container
  if (toolbarEl) {
    const titleMap = [
      ['button.ql-bold', '加粗'],
      ['button.ql-italic', '斜体'],
      ['button.ql-underline', '下划线'],
      ['button.ql-strike', '删除线'],
      ['button.ql-list[value="ordered"]', '有序列表'],
      ['button.ql-list[value="bullet"]', '无序列表'],
      ['button.ql-link', '插入链接'],
      ['button.ql-image', '插入图片'],
      ['button.ql-blockquote', '引用'],
      ['button.ql-code-block', '代码块'],
      ['button.ql-clean', '清除格式'],
      ['.ql-picker.ql-header .ql-picker-label', '标题级别'],
      ['.ql-picker.ql-color .ql-picker-label', '文字颜色'],
      ['.ql-picker.ql-background .ql-picker-label', '背景颜色'],
      ['.ql-picker.ql-align .ql-picker-label', '对齐方式'],
    ]

    titleMap.forEach(([selector, title]) => {
      toolbarEl.querySelectorAll(selector).forEach((el) => {
        el.setAttribute('title', title)
        el.setAttribute('data-tip', title)
      })
    })

  }

}

const submitNews = async () => {
  submitError.value = ''
  submitSuccess.value = ''

  const prepared = buildSubmitPayload()
  const title = prepared.title
  if (!title) {
    submitError.value = '请填写新闻标题'
    return
  }
  if (title.length > 50) {
    submitError.value = '新闻标题需在50字以内'
    return
  }

  const category = prepared.category
  if (!category) {
    submitError.value = '请选择有效分类'
    return
  }

  const plain = prepared.plain
  if (!plain) {
    submitError.value = '请填写新闻正文'
    return
  }

  if (isEditMode.value) {
    if (!hasEditChanges.value) {
      return
    }
  }

  autoFillDescription()

  const payload = prepared.payload

  submitting.value = true
  try {
    const request = isEditMode.value
      ? axios.put(`${API_BASE}/news/${editNewsId.value}`, payload, {
          headers: {
            ...authHeaders(),
          },
        })
      : axios.post(`${API_BASE}/news/`, payload, {
          headers: {
            ...authHeaders(),
          },
        })

    const res = await request

    if (res.data?.code !== 200) {
      throw new Error(res.data?.message || '发布失败')
    }

    const successMessage = isEditMode.value ? '更新成功' : '发布成功'
    submitSuccess.value = successMessage
    showToast(successMessage)
    setTimeout(() => {
      router.push(isEditMode.value ? '/profile' : '/')
    }, 2000)
  } catch (err) {
    submitError.value = err.response?.data?.message || err.response?.data?.detail || err.message || '发布失败'
  } finally {
    submitting.value = false
  }
}

const runWritingAssistant = async () => {
  const demand = assistantPrompt.value.trim()
  if (!demand || assistantLoading.value) {
    return
  }

  assistantError.value = ''
  assistantLoading.value = true
  try {
    const rawHtml = quill?.root?.innerHTML || ''
    const plain = stripHtml(rawHtml)
    const response = await axios.post(`${API_BASE}/ai/news/draft/suggest`, {
      title: form.value.title.trim() || demand.slice(0, 30),
      category_name: categories.value.find((item) => String(item.id) === form.value.categoryId)?.name || '头条',
      content: [demand, plain].filter(Boolean).join('\n\n'),
      description: form.value.description.trim() || null,
    }, {
      headers: {
        ...authHeaders(),
      },
    })

    assistantResult.value = response?.data?.data || null
  } catch (err) {
    assistantError.value = err.response?.data?.message || err.response?.data?.detail || 'AI写作助手调用失败'
  } finally {
    assistantLoading.value = false
  }
}

const applyTitleSuggestion = (value) => {
  if (!value) return
  form.value.title = value
}

const applyDescriptionSuggestion = () => {
  const value = assistantResult.value?.description_suggestion || ''
  if (!value) return
  form.value.description = value
}

const insertSuggestionToEditor = (text) => {
  if (!quill || !text) return
  const range = quill.getSelection(true)
  const insertIndex = range ? range.index : quill.getLength()
  const content = text.endsWith('\n') ? text : `${text}\n`
  quill.insertText(insertIndex, content, 'user')
  quill.setSelection(insertIndex + content.length, 0)
}

const handlePublishClickFromNav = () => {
  handlePublishClick()
}

const handleCancel = () => {
  if (window.history.length > 1) {
    router.back()
    return
  }
  goHome()
}

onMounted(() => {
  restoreCurrentUser()
  ensureAuthenticated('')
  Promise.all([fetchCategories(), initEditor()]).then(() => {
    loadEditNews()
  })
})

watch(form, () => {
  updateEditDirtyState()
}, { deep: true })

onBeforeUnmount(() => {
  if (toastTimer) {
    clearTimeout(toastTimer)
    toastTimer = null
  }
  quill = null
})
</script>

<template>
  <div class="publish-layout">
    <TopNavBar
      :current-user="currentUser"
      @logo-click="goHome"
      @profile-click="goToProfile"
      @logout-click="logout"
      @publish-click="handlePublishClickFromNav"
      @login-click="goHome"
    />

    <main class="publish-main">
      <div class="publish-shell">
        <div class="publish-card">
        <div class="hero-head">
          <h1>{{ isEditMode ? '编辑新闻' : '新闻发布' }}</h1>
        </div>

        <p v-if="loadingEditData" class="feedback">正在加载待编辑内容...</p>

        <div class="form-grid">
          <input
            v-model="form.title"
            class="title-input"
            type="text"
            placeholder="请输入新闻标题（必填，50字以内）"
            maxlength="50"
          />

          <div class="category-field">
            <div class="category-list" :class="{ loading: loadingCategories }">
              <p class="news_category">分类：</p>
              <button
                v-for="cat in categories"
                :key="cat.id"
                type="button"
                class="category-btn"
                :class="{ active: String(cat.id) === form.categoryId }"
                :disabled="loadingCategories"
                @click="form.categoryId = String(cat.id)"
              >
                {{ cat.name }}
              </button>
            </div>
          </div>

          <input
            v-model="form.description"
            class="summary-input"
            type="text"
            placeholder="请输入摘要（可选，不填将自动截取正文前100字）"
            maxlength="180"
          />

          <div class="cover-row">
            <button class="upload-btn" type="button" :disabled="coverUploading" @click="uploadCoverImage">
              {{ coverUploading ? '上传中...' : '上传封面图（可选）' }}
            </button>
            <div v-if="form.image" class="cover-preview">
              <img :src="toAbsoluteUrl(form.image)" alt="封面缩略图" />
              <button class="remove-cover" type="button" @click="form.image = ''">移除</button>
            </div>
          </div>
        </div>

        <div class="editor-wrap">
          <div ref="editorRef" class="editor"></div>
        </div>

        <p v-if="submitError" class="feedback error">{{ submitError }}</p>
        <div class="actions">
          <button class="btn primary" :disabled="!canSubmit" @click="submitNews">
            {{ submitting ? (isEditMode ? '保存中...' : '发布中...') : (isEditMode ? '保存修改' : '确认发布') }}
          </button>
          <button class="btn" :disabled="submitting" @click="handleCancel">取消</button>
        </div>
        </div>

        <aside class="assistant-panel">
          <div class="assistant-head">
            <h3>AI写作助手</h3>
            <p>输入你的写作需求，快速生成标题、摘要和正文建议</p>
          </div>

          <textarea
            v-model="assistantPrompt"
            rows="4"
            class="assistant-input"
            placeholder="例如：帮我写一篇关于新能源汽车价格战的新闻稿，重点突出消费者影响"
          ></textarea>

          <button
            type="button"
            class="assistant-run"
            :disabled="assistantLoading"
            @click="runWritingAssistant"
          >
            {{ assistantLoading ? '生成中...' : '生成写作建议' }}
          </button>

          <p v-if="assistantError" class="assistant-error">{{ assistantError }}</p>

          <div v-if="assistantResult" class="assistant-result">
            <section v-if="assistantResult.title_suggestions?.length" class="assistant-block">
              <h4>标题建议</h4>
              <ul>
                <li
                  v-for="(item, idx) in assistantResult.title_suggestions"
                  :key="`title-${idx}`"
                  class="assistant-item clickable"
                  @click="applyTitleSuggestion(item)"
                >
                  <span>{{ item }}</span>
                </li>
              </ul>
            </section>

            <section v-if="assistantResult.description_suggestion" class="assistant-block">
              <h4>摘要建议</h4>
              <p class="assistant-item clickable" @click="applyDescriptionSuggestion">{{ assistantResult.description_suggestion }}</p>
            </section>

            <section v-if="assistantResult.content_suggestions?.length" class="assistant-block">
              <h4>正文建议</h4>
              <ul>
                <li
                  v-for="(item, idx) in assistantResult.content_suggestions"
                  :key="`content-${idx}`"
                  class="assistant-item clickable"
                  @click="insertSuggestionToEditor(item)"
                >
                  <p>{{ item }}</p>
                </li>
              </ul>
            </section>
          </div>
        </aside>
      </div>
    </main>

    <transition name="toast-fade">
      <div v-if="toastVisible" class="toast toast-success">{{ toastMessage }}</div>
    </transition>
  </div>
</template>

<style scoped>
.news_category{
  font-size: 16px;
  color: #334155;
  margin-left: 8px;
}

.publish-layout {
  min-height: 100vh;
  background: linear-gradient(180deg, #f8f9fb 0%, #f0f3f7 100%);
  color-scheme: light;
}

.publish-main {
  width: 1170px;
  margin: 76px auto 0;
  padding: 24px 16px;
}

.publish-card {
  background: linear-gradient(145deg, #ffffff 0%, #fbfcff 100%);
  border-radius: 18px;
  padding: 34px;
  box-shadow: 0 18px 36px rgba(20, 28, 45, 0.1);
  flex: 1;
}

.publish-shell {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.assistant-panel {
  width: 330px;
  flex-shrink: 0;
  position: sticky;
  top: 88px;
  background: linear-gradient(150deg, #f8fafc 0%, #f1f5f9 100%);
  color: #1e293b;
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.12);
  text-align: left;
}

.assistant-head h3 {
  margin: 0;
  font-size: 20px;
}

.assistant-head p {
  margin: 8px 0 12px;
  font-size: 13px;
  line-height: 1.5;
  color: #64748b;
}

.assistant-input {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #f3f4f6;
  color: #1e293b;
  resize: vertical;
  padding: 10px;
  font-size: 13px;
}

.assistant-run {
  margin-top: 10px;
  width: 100%;
  height: 36px;
  border: none;
  border-radius: 9px;
  background: linear-gradient(90deg, #0ea5e9, #2563eb);
  color: #fff;
  cursor: pointer;
  font-weight: 600;
}

.assistant-run:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.assistant-error {
  margin: 10px 0 0;
  padding: 8px;
  background: rgba(248, 113, 113, 0.2);
  border: 1px solid rgba(248, 113, 113, 0.35);
  border-radius: 8px;
  color: #fecaca;
  font-size: 12px;
}

.assistant-result {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.assistant-block {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 10px;
}

.assistant-block h4 {
  margin: 0 0 8px;
  font-size: 14px;
  color: #1e293b;
}

.assistant-block ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.assistant-block li {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  padding: 8px;
}

.assistant-block span,
.assistant-block p {
  display: block;
  margin: 0;
  color: #334155;
  line-height: 1.5;
  font-size: 13px;
}

.assistant-item.clickable {
  cursor: pointer;
  transition: all 0.16s ease;
}

.assistant-item.clickable:hover {
  border-color: #93c5fd;
  background: #eff6ff;
  box-shadow: inset 0 0 0 1px #bfdbfe;
}

.hero-head {
  text-align: left;
  margin-bottom: 40px;
  margin-top: 16px;
  padding: 10px 14px;
  border-left: 5px solid #ff4d4f;
  background: linear-gradient(90deg, #fff4f4 0%, #fff 100%);
  border-radius: 10px;
}

.publish-card h1 {
  margin: 0;
  color: #1f2937;
  font-size: 34px;
  line-height: 1.18;
  letter-spacing: 0.5px;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
  margin-bottom: 16px;
}

.title-input,
.summary-input {
  width: 100%;
  border: 1px solid #d9dee7;
  border-radius: 10px;
  padding: 0 14px;
  transition: border-color 0.2s;
  box-sizing: border-box;
  color: #1f2937;
}

.title-input {
  height: 52px;
  font-size: 22px;
  font-weight: 700;
  background: #eef3fb;
}

.summary-input {
  height: 40px;
  font-size: 14px;
  background: #f6f8fb;
}

.title-input::placeholder,
.summary-input::placeholder {
  color: #94a3b8;
}

.title-input:focus,
.summary-input:focus {
  border-color: #2f6ff5;
  outline: none;
}

.category-field {
  align-self: stretch;
}

.category-list {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  gap: 10px;
  max-height: none;
  overflow: visible;
  padding-right: 2px;
}

.cover-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.upload-btn {
  border: 1px dashed #9cb3e9;
  background: #f1f6ff;
  color: #2456c8;
  border-radius: 10px;
  height: 38px;
  padding: 0 14px;
  font-size: 13px;
  cursor: pointer;
}

.upload-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.cover-preview {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.cover-preview img {
  width: 86px;
  height: 56px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid #d3deef;
}

.remove-cover {
  border: 1px solid #d6dceb;
  background: #ffffff;
  color: #5b6472;
  border-radius: 8px;
  height: 30px;
  padding: 0 10px;
  font-size: 12px;
  cursor: pointer;
}

.category-list.loading {
  opacity: 0.7;
}

.category-btn {
  text-align: center;
  padding: 8px 16px;
  border: 1px solid #d8dee9;
  background: #f8fafc;
  border-radius: 999px;
  color: #374151;
  cursor: pointer;
  transition: all 0.18s ease;
  color: #334155;
  font-size: 13px;
  line-height: 1;
}

.category-btn:hover {
  border-color: #b3c6fa;
  background: #eef4ff;
  transform: translateY(-1px);
}

.category-btn.active {
  border-color: #2f6ff5;
  background: linear-gradient(90deg, #2f6ff5 0%, #4a86ff 100%);
  color: #ffffff;
  font-weight: 700;
  box-shadow: 0 6px 14px rgba(47, 111, 245, 0.25);
}

.editor-wrap {
  border: 1px solid #d9dee7;
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
}

:deep(.ql-toolbar.ql-snow) {
  border: none;
  border-bottom: 1px solid #e7ebf2;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-start;
  gap: 8px;
  padding: 10px 12px;
}

:deep(.ql-toolbar.ql-snow .ql-formats) {
  margin-right: 0;
  display: flex;
  align-items: flex-end;
  gap: 4px;
}

:deep(.ql-container.ql-snow) {
  border: none;
  min-height: 340px;
  font-size: 15px;
}

:deep(.ql-toolbar.ql-snow button) {
  width: 44px;
  height: 36px;
  padding: 6px 8px;
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative;
  overflow: visible;
}

:deep(.ql-toolbar.ql-snow button svg) {
  width: 16px;
  height: 16px;
}

:deep(.ql-toolbar .ql-stroke) {
  stroke: #374151;
}

:deep(.ql-toolbar .ql-fill) {
  fill: #374151;
}

:deep(.ql-toolbar.ql-snow .ql-picker) {
  height: 36px;
}

:deep(.ql-toolbar.ql-snow .ql-picker-label) {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  position: relative;
  overflow: visible;
}

:deep(.ql-toolbar [data-tip]:hover::after),
:deep(.ql-toolbar [data-tip]:focus-visible::after) {
  content: attr(data-tip);
  position: absolute;
  left: 50%;
  top: calc(100% + 8px);
  transform: translateX(-50%);
  background: rgba(17, 24, 39, 0.96);
  color: #fff;
  font-size: 12px;
  line-height: 1;
  padding: 6px 8px;
  border-radius: 6px;
  white-space: nowrap;
  z-index: 30;
  pointer-events: none;
}

:deep(.ql-toolbar [data-tip]:hover::before),
:deep(.ql-toolbar [data-tip]:focus-visible::before) {
  content: '';
  position: absolute;
  left: 50%;
  top: calc(100% + 2px);
  transform: translateX(-50%);
  border-width: 4px;
  border-style: solid;
  border-color: transparent transparent rgba(17, 24, 39, 0.96) transparent;
  z-index: 30;
  pointer-events: none;
}

.feedback {
  margin: 14px 0 0;
  font-size: 14px;
}

.feedback.error {
  color: #c43a3a;
}

.feedback.success {
  color: #198754;
}

.toast {
  position: fixed;
  left: 50%;
  bottom: 72px;
  transform: translateX(-50%);
  z-index: 1000;
  min-width: 200px;
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

.actions {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}

.btn {
  height: 40px;
  padding: 0 18px;
  border-radius: 8px;
  border: 1px solid #cfd6e1;
  background: #eef2f7;
  color: #334155;
  cursor: pointer;
  font-weight: 500;
}

.btn.primary {
  border-color: #2f6ff5;
  background: #2f6ff5;
  color: #fff;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

@media (max-width: 1200px) {
  .publish-main {
    width: 100%;
  }

  .publish-shell {
    flex-direction: column;
  }

  .assistant-panel {
    width: 100%;
    position: static;
  }
}

@media (max-width: 768px) {
  .publish-main {
    margin-top: 64px;
    padding: 12px;
  }

  .publish-card {
    padding: 16px;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .title-input {
    height: 46px;
    font-size: 18px;
  }
}
</style>
