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
    path: '/users',
    name: 'UserManage',
    component: UserManage
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

export default router
