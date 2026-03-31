<script setup>
import { onMounted } from 'vue'
import TopNavBar from '../components/TopNavBar.vue'
import { useTopNavAuth } from '../composables/useTopNavAuth'

const {
  currentUser,
  restoreCurrentUser,
  logout,
  goHome,
  goToProfile,
  handlePublishClick,
  ensureAuthenticated,
} = useTopNavAuth()

const handlePublishClickFromNav = () => {
  handlePublishClick()
}

onMounted(() => {
  restoreCurrentUser()
  ensureAuthenticated('')
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
      <div class="publish-card">
        <h1>发布新闻</h1>
        <p>发布模块已接入统一路由，后续可在这里接入完整表单与接口提交。</p>
      </div>
    </main>
  </div>
</template>

<style scoped>
.publish-layout {
  min-height: 100vh;
  background: #f4f5f6;
}

.publish-main {
  width: 1170px;
  margin: 76px auto 0;
  padding: 24px 16px;
}

.publish-card {
  background: #fff;
  border-radius: 10px;
  padding: 32px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.publish-card h1 {
  margin: 0 0 12px;
  color: #222;
}

.publish-card p {
  margin: 0;
  color: #666;
  line-height: 1.7;
}
</style>
