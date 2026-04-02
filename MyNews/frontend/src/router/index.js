import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import NewsDetail from '../views/NewsDetail.vue'
import UserManage from '../views/UserManage.vue'
import UserProfile from '../views/UserProfile.vue'
import PublishNews from '../views/PublishNews.vue'
import SearchResults from '../views/SearchResults.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/news/:id',
    name: 'NewsDetail',
    component: NewsDetail,
    props: true
  },
  {
    path: '/admin/users',
    name: 'AdminUserManage',
    component: UserManage,
    meta: { requiresBackOffice: true }
  },
  {
    path: '/profile',
    name: 'UserProfile',
    component: UserProfile
  },
  {
    path: '/publish',
    name: 'PublishNews',
    component: PublishNews
  },
  {
    path: '/search',
    name: 'SearchResults',
    component: SearchResults
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, _, next) => {
  if (!to.meta?.requiresBackOffice) {
    next()
    return
  }

  const raw = localStorage.getItem('currentUser')
  if (!raw) {
    next('/profile')
    return
  }

  try {
    const currentUser = JSON.parse(raw)
    if (['admin', 'reviewer'].includes(currentUser?.role)) {
      next()
      return
    }
  } catch (e) {
    // ignore parse error and continue to fallback redirect
  }

  next('/profile')
})

export default router
