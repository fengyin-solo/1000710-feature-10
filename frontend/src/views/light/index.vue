<template>
  <section class="page" data-module="light">
    <header class="page-head">
      <div>
        <h2>照明设施管理</h2>
        <p class="page-desc">维护照明设施，围绕设施编号、灯杆编号、灯具类型、所在道路做登记、筛选与状态流转，并保留每根灯杆的巡检记录。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记照明设施</button>
        <button class="btn" type="button" @click="exportRows">导出照明设施清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>最近巡检</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td>{{ formatLatest(row['最近巡检']) }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">查看详情</button>
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 2" class="empty-state">暂无照明设施数据，可先登记照明设施</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条照明设施记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="showCreate" class="modal-mask" @click.self="showCreate = false">
      <form class="modal-card" @submit.prevent="submitCreate">
        <h3 class="modal-title">登记照明设施</h3>
        <label v-for="field in createFields" :key="field" class="filter-item">
          <span>{{ field }}</span>
          <input v-model="createForm[field]" :placeholder="`请输入${field}`" />
        </label>
        <p v-if="createError" class="error-text">{{ createError }}</p>
        <div class="modal-actions">
          <button class="btn primary" type="submit">确认登记</button>
          <button class="btn ghost" type="button" @click="showCreate = false">取消</button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, any>

const ENDPOINT = '/api/light'
const columns = ["设施编号", "灯杆编号", "灯具类型", "所在道路", "亮灯率", "上次检修日", "责任班组", "设施状态"]
const actions = ["安排检修", "确认正常", "停用设施"]
const statuses = ["待检修", "正常亮灯", "缺亮待修", "已停用"]
const stats = [{"label": "在册照明设施", "value": 0}, {"label": "缺亮待修", "value": 0}, {"label": "平均亮灯率", "value": 0}]
// 列表筛选条件与后端查询参数的对应关系
const PARAM_MAP: Record<string, string> = { "设施编号": "keyword", "灯杆编号": "pole", "灯具类型": "lamp" }
const SCROLL_KEY = 'light-list-scroll'

const route = useRoute()
const router = useRouter()

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const showCreate = ref(false)
const createError = ref('')
const createFields = ["设施编号", "灯杆编号", "灯具类型"]
const createForm = ref<Record<string, string>>({})

// 从地址栏恢复筛选条件：详情页返回时列表保持上次的查询状态
for (const field of filterFields) {
  const value = route.query[field]
  if (typeof value === 'string' && value) {
    filters.value[field] = value
  }
}

function currentFilterQuery() {
  const query: Record<string, string> = {}
  for (const field of filterFields) {
    const value = (filters.value[field] ?? '').trim()
    if (value) {
      query[field] = value
    }
  }
  return query
}

function formatLatest(latest: Row | null | undefined) {
  if (!latest) {
    return '—'
  }
  return `${latest['巡检日期']} · ${latest['本次结论']}`
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = {}
  createError.value = ''
  showCreate.value = true
}

async function submitCreate() {
  createError.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: createForm.value }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      createError.value = payload.message ?? '照明设施登记失败，请检查后重试'
      return
    }
    showCreate.value = false
    noticeMessage.value = payload.message ?? '照明设施已登记'
    await reload()
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '照明设施登记失败'
  }
}

function openDetail(row: Row) {
  // 把当前筛选条件带进详情页地址，返回时原样带回列表
  router.push({ name: 'light-detail', params: { id: row.id }, query: currentFilterQuery() })
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('照明设施动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '照明设施操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  for (const field of filterFields) {
    const value = (filters.value[field] ?? '').trim()
    if (value) {
      params.set(PARAM_MAP[field] ?? field, value)
    }
  }
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw new Error('照明设施列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '照明设施列表读取失败'
  }
}

onBeforeRouteLeave(() => {
  sessionStorage.setItem(SCROLL_KEY, String(window.scrollY))
})

onMounted(async () => {
  await reload()
  // 数据渲染完再恢复滚动位置，避免列表还没撑开时滚不到原位
  const saved = sessionStorage.getItem(SCROLL_KEY)
  if (saved) {
    sessionStorage.removeItem(SCROLL_KEY)
    await nextTick()
    window.scrollTo(0, Number(saved))
  }
})
</script>

<style scoped>
.notice-text { color: #067647; }
.modal-mask { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: 10; }
.modal-card { background: #fff; border-radius: 8px; padding: 16px 20px; width: 360px; display: flex; flex-direction: column; gap: 10px; }
.modal-title { margin: 0; font-size: 15px; }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; }
</style>
