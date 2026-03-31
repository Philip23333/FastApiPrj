<script setup>
import { ref, watch } from 'vue'
import axios from 'axios'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  }
})

const emit = defineEmits(['update:visible', 'success'])

const isLoginMode = ref(true)
const authForm = ref({ username: '', password: '' })
const authError = ref('')

watch(
  () => props.visible,
  (newVal) => {
    if (newVal) {
      authError.value = ''
      authForm.value = { username: '', password: '' }
      isLoginMode.value = true
    }
  }
)

const closeModal = () => {
  emit('update:visible', false)
}

const toggleAuthMode = () => {
  isLoginMode.value = !isLoginMode.value
  authError.value = ''
  authForm.value = { username: '', password: '' }
}

const submitAuth = async () => {
  authError.value = ''
  if (!authForm.value.username || !authForm.value.password) {
    authError.value = '请填写用户名和密码'
    return
  }

  const url = isLoginMode.value
    ? 'http://127.0.0.1:8080/users/login'
    : 'http://127.0.0.1:8080/users/register'

  try {
    const res = await axios.post(url, authForm.value)
    if (isLoginMode.value && res.data && res.data.code === 200) {
      const loginData = res.data.data || {}
      emit('success', {
        user: loginData.user || null,
        accessToken: loginData.access_token || ''
      })
      closeModal()
      return
    }

    if (!isLoginMode.value && res.data && (res.data.code === 200 || res.data.code === 201)) {
      authError.value = '注册成功，请登录'
      isLoginMode.value = true
      authForm.value = { username: authForm.value.username, password: '' }
      return
    }

    authError.value = '操作失败'
  } catch (err) {
    console.error(err)
    authError.value = err.response?.data?.message || err.response?.data?.detail || '操作失败'
  }
}
</script>

<template>
  <div v-if="visible" class="auth-modal-overlay" @click.self="closeModal">
    <div class="auth-modal">
      <div class="auth-close" @click="closeModal">×</div>
      <h2 class="auth-title">{{ isLoginMode ? '账号登录' : '账号注册' }}</h2>

      <form class="auth-form" @submit.prevent="submitAuth">
        <div class="input-group">
          <input v-model="authForm.username" type="text" placeholder="请输入用户名" />
        </div>
        <div class="input-group">
          <input v-model="authForm.password" type="password" placeholder="请输入密码" />
        </div>
        <div class="auth-error" v-if="authError">{{ authError }}</div>

        <button type="submit" class="submit-btn">
          {{ isLoginMode ? '登录' : '注册' }}
        </button>

        <div class="auth-switch">
          {{ isLoginMode ? '没有账号？' : '已有账号？' }}
          <a @click="toggleAuthMode">{{ isLoginMode ? '去注册' : '去登录' }}</a>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.auth-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(4px);
  z-index: 2000;
  display: flex;
  justify-content: center;
  align-items: center;
  animation: fadeIn 0.2s ease-out;
}

.auth-modal {
  background: #fff;
  width: 380px;
  padding: 40px;
  border-radius: 12px;
  position: relative;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1), 0 1px 8px rgba(0, 0, 0, 0.06);
  transform: translateY(0);
  animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.auth-close {
  position: absolute;
  top: 16px;
  right: 20px;
  font-size: 26px;
  color: #c2c2c2;
  cursor: pointer;
  line-height: 1;
  transition: color 0.2s;
}

.auth-close:hover {
  color: #666;
}

.auth-title {
  margin-top: 0;
  margin-bottom: 30px;
  font-size: 22px;
  font-weight: 600;
  text-align: center;
  color: #1f1f1f;
  letter-spacing: 1px;
}
.login-text {
  color: #406599;
  font-size: 14px;
  cursor: pointer;
}

.input-group {
  margin-bottom: 22px;
}

.input-group input {
  width: 100%;
  padding: 14px 16px;
  background-color: #f7f7f7;
  border: 1px solid transparent;
  border-radius: 8px;
  font-size: 15px;
  color: #333;
  box-sizing: border-box;
  transition: all 0.3s ease;
}

.input-group input::placeholder {
  color: #aaa;
}

.input-group input:focus {
  outline: none;
  background-color: #fff;
  border-color: #f04142;
  box-shadow: 0 0 0 3px rgba(240, 65, 66, 0.1);
}

.auth-error {
  color: #f04142;
  font-size: 13px;
  margin-top: -10px;
  margin-bottom: 20px;
  padding-left: 2px;
}

.submit-btn {
  width: 100%;
  background: linear-gradient(90deg, #f04142, #ff5e5e);
  color: #fff;
  border: none;
  padding: 14px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 500;
  letter-spacing: 1px;
  cursor: pointer;
  box-shadow: 0 4px 10px rgba(240, 65, 66, 0.2);
  transition: all 0.3s ease;
}

.submit-btn:hover {
  background: linear-gradient(90deg, #d83536, #f04142);
  box-shadow: 0 6px 14px rgba(240, 65, 66, 0.3);
  transform: translateY(-1px);
}

.submit-btn:active {
  transform: translateY(1px);
  box-shadow: 0 2px 6px rgba(240, 65, 66, 0.2);
}

.auth-switch {
  margin-top: 25px;
  text-align: center;
  font-size: 14px;
  color: #888;
}

.auth-switch a {
  color: #1e6fff;
  font-weight: 500;
  cursor: pointer;
  margin-left: 5px;
  transition: color 0.2s;
}

.auth-switch a:hover {
  color: #0b51cc;
  text-decoration: underline;
}
</style>