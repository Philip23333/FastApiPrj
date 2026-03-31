<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import AuthModal from './components/AuthModal.vue'
import { useTopNavAuth } from './composables/useTopNavAuth'

const router = useRouter()
const showGlobalAuthModal = ref(false)
const { handleAuthSuccess } = useTopNavAuth()
const pendingTargetPath = ref('')
const pendingFallbackPath = ref('')
const authSucceeded = ref(false)
const toastVisible = ref(false)
const toastMessage = ref('')
let toastTimer = null

const showToast = (message, duration = 1800) => {
  toastMessage.value = message
  toastVisible.value = true
  if (toastTimer) {
    clearTimeout(toastTimer)
  }
  toastTimer = setTimeout(() => {
    toastVisible.value = false
  }, duration)
}

const handleAuthRequired = (event) => {
  const message = event?.detail?.message || '请先登录后再继续操作。'
  pendingTargetPath.value = event?.detail?.targetPath || ''
  pendingFallbackPath.value = event?.detail?.fallbackPath || ''
  authSucceeded.value = false
  showToast(message)
  showGlobalAuthModal.value = true
}

onMounted(() => {
  window.addEventListener('auth-required', handleAuthRequired)
})

onBeforeUnmount(() => {
  window.removeEventListener('auth-required', handleAuthRequired)
  if (toastTimer) {
    clearTimeout(toastTimer)
  }
})

const handleGlobalAuthSuccess = (payload) => {
  handleAuthSuccess(payload)
  authSucceeded.value = true
  showGlobalAuthModal.value = false
  if (pendingTargetPath.value) {
    router.push(pendingTargetPath.value)
  }
  pendingTargetPath.value = ''
  pendingFallbackPath.value = ''
}

const handleGlobalAuthVisibleChange = (visible) => {
  showGlobalAuthModal.value = visible
  if (!visible && !authSucceeded.value && pendingFallbackPath.value) {
    router.push(pendingFallbackPath.value)
  }
  if (!visible) {
    pendingTargetPath.value = ''
    pendingFallbackPath.value = ''
  }
}
</script>

<template>
  <router-view></router-view>
  <transition name="toast-fade">
    <div v-if="toastVisible" class="global-toast">{{ toastMessage }}</div>
  </transition>
  <AuthModal
    v-model:visible="showGlobalAuthModal"
    @update:visible="handleGlobalAuthVisibleChange"
    @success="handleGlobalAuthSuccess"
  />
</template>

<style>
/* 全局充当 Base CSS */
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

.global-toast {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 3000;
  background: rgba(30, 30, 30, 0.92);
  color: #fff;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 14px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-6px);
}
</style>
