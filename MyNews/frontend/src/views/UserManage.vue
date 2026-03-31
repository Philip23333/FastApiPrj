<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

// 基础 API 地址
const API_BASE = 'http://127.0.0.1:8080/users'

// 状态
const users = ref([])
const loading = ref(false)
const message = ref('')

// 表单弹窗状态
const showModal = ref(false)
const isEditing = ref(false)
const currentUserId = ref(null)

// 用户表单数据
const userForm = ref({
  username: '',
  password: '', // 仅创建时需要
  nickname: '',
  phone: '',
  bio: ''
})

// 获取用户列表 (R)
const fetchUsers = async () => {
  loading.value = true
  try {
    const res = await axios.get(`${API_BASE}/?skip=0&limit=100`)
    if (res.data.code === 200) {
      users.value = res.data.data
    }
  } catch (error) {
    console.error("获取用户失败:", error)
    message.value = "获取用户列表失败"
  } finally {
    loading.value = false
  }
}

// 打开新建用户弹窗
const openCreateModal = () => {
  isEditing.value = false
  userForm.value = { username: '', password: '', nickname: '', phone: '', bio: '' }
  showModal.value = true
}

// 打开编辑用户弹窗
const openEditModal = (user) => {
  isEditing.value = true
  currentUserId.value = user.id
  userForm.value = {
    username: user.username, // 一般不让改用户名，但放进去展示
    password: '',            // 留空代表不修改密码
    nickname: user.nickname || '',
    phone: user.phone || '',
    bio: user.bio || ''
  }
  showModal.value = true
}

// 保存用户 (C / U)
const saveUser = async () => {
  try {
    if (isEditing.value) {
      // 提取被更新的字段，排除未填写的可选字段
      const updateData = {}
      if (userForm.value.nickname) updateData.nickname = userForm.value.nickname
      if (userForm.value.phone) updateData.phone = userForm.value.phone
      if (userForm.value.bio) updateData.bio = userForm.value.bio
      if (userForm.value.password) updateData.password = userForm.value.password

      const res = await axios.put(`${API_BASE}/${currentUserId.value}`, updateData)
      if (res.data.code === 200) {
        message.value = "更新成功！"
      }
    } else {
      // 新建逻辑
      const res = await axios.post(`${API_BASE}/`, {
        username: userForm.value.username,
        password: userForm.value.password,
        nickname: userForm.value.nickname,
        phone: userForm.value.phone,
        bio: userForm.value.bio
      })
      if (res.data.code === 200) {
        message.value = "创建成功！"
      }
    }
    showModal.value = false
    fetchUsers() // 刷新列表
  } catch (error) {
    console.error("保存失败:", error)
    message.value = error.response?.data?.detail || "保存失败，请检查输入"
  }
}

// 删除用户 (D)
const deleteUser = async (id) => {
  if (!confirm("确定要删除该用户吗？")) return
  
  try {
    const res = await axios.delete(`${API_BASE}/${id}`)
    if (res.data.code === 200) {
      message.value = "删除成功！"
      fetchUsers()
    }
  } catch (error) {
    console.error("删除失败:", error)
    message.value = "删除失败"
  }
}

onMounted(() => {
  fetchUsers()
})
</script>

<template>
  <div class="user-manage">
    <div class="header">
      <h2>用户管理模块</h2>
      <button class="btn-primary" @click="openCreateModal">新增用户</button>
    </div>
    
    <div v-if="message" class="alert">{{ message }}</div>

    <!-- 用户列表 -->
    <div v-if="loading">加载中...</div>
    <table v-else class="user-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>用户名</th>
          <th>昵称</th>
          <th>手机号</th>
          <th>注册时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="user in users" :key="user.id">
          <td>{{ user.id }}</td>
          <td>{{ user.username }}</td>
          <td>{{ user.nickname || '-' }}</td>
          <td>{{ user.phone || '-' }}</td>
          <td>{{ new Date(user.created_at).toLocaleString() }}</td>
          <td>
            <button class="btn-edit" @click="openEditModal(user)">编辑</button>
            <button class="btn-delete" @click="deleteUser(user.id)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- 弹窗表单 -->
    <div v-if="showModal" class="modal-overlay">
      <div class="modal">
        <h3>{{ isEditing ? '编辑用户' : '新建用户' }}</h3>
        
        <div class="form-group">
          <label>用户名 (必填)</label>
          <input v-model="userForm.username" type="text" :disabled="isEditing" />
        </div>
        <div class="form-group">
          <label>密码</label>
          <input v-model="userForm.password" type="password" :placeholder="isEditing ? '留空则不修改' : '必填'" />
        </div>
        <div class="form-group">
          <label>昵称</label>
          <input v-model="userForm.nickname" type="text" />
        </div>
        <div class="form-group">
          <label>手机号</label>
          <input v-model="userForm.phone" type="text" />
        </div>
        <div class="form-group">
          <label>个人简介</label>
          <textarea v-model="userForm.bio"></textarea>
        </div>

        <div class="modal-actions">
          <button @click="showModal = false">取消</button>
          <button class="btn-primary" @click="saveUser">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.user-manage {
  max-width: 1000px;
  margin: 0 auto;
  padding: 20px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.alert {
  padding: 10px;
  background-color: #f8d7da;
  color: #721c24;
  margin-bottom: 15px;
  border-radius: 4px;
}
.user-table {
  width: 100%;
  border-collapse: collapse;
}
.user-table th, .user-table td {
  border: 1px solid #ddd;
  padding: 10px;
  text-align: left;
}
.user-table th {
  background-color: #f4f4f4;
}
.btn-primary { background: #4CAF50; color: white; border: none; padding: 8px 16px; cursor: pointer; border-radius: 4px; }
.btn-edit { background: #2196F3; color: white; border: none; padding: 5px 10px; cursor: pointer; margin-right: 5px; border-radius: 3px; }
.btn-delete { background: #f44336; color: white; border: none; padding: 5px 10px; cursor: pointer; border-radius: 3px; }

/* 模态窗样式 */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
}
.modal {
  background: white;
  padding: 20px;
  border-radius: 8px;
  width: 400px;
  max-width: 90%;
  color: #333;
}
.form-group {
  margin-bottom: 15px;
  display: flex;
  flex-direction: column;
}
.form-group label {
  margin-bottom: 5px;
}
.form-group input, .form-group textarea {
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}
</style>
