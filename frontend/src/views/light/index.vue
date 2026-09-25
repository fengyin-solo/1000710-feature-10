<template>
  <section class="page" data-module="light">
    <header class="page-head">
      <div>
        <h2>照明设施管理</h2>
        <p class="page-desc">维护照明设施台账，巡检记录留档后，台账与详情页会同步展示最近一次结论。</p>
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

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label class="filter-item">
        <span>设施编号 / 灯杆编号</span>
        <input v-model="filters.keyword" placeholder="按设施编号或灯杆编号检索" />
      </label>
      <label class="filter-item">
        <span>灯具类型</span>
        <input v-model="filters.lamp_type" placeholder="按灯具类型检索" />
      </label>
      <label class="filter-item">
        <span>设施状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
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
          <td>
            <span v-if="row.最近巡检">{{ row.最近巡检.巡检日期 }} · {{ row.最近巡检.本次结论 }}</span>
            <span v-else class="muted">暂无巡检记录</span>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">巡检详情</button>
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
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Inspection = {
  巡检日期?: string
  灯具类型?: string
  上次更换时间?: string
  本次结论?: string
  巡检人?: string
  备注?: string
}
type Row = Record<string, string | number | null> & { 最近巡检?: Inspection | null }

const ENDPOINT = '/api/light'
const columns = ["设施编号", "灯杆编号", "灯具类型", "所在道路", "亮灯率", "上次检修日", "责任班组", "设施状态"]
const actions = ["安排检修", "确认正常", "停用设施"]
const statuses = ["待检修", "正常亮灯", "缺亮待修", "已停用"]
const stats = [{"label": "在册照明设施", "value": 0}, {"label": "缺亮待修", "value": 0}, {"label": "平均亮灯率", "value": 0}]

const route = useRoute()
const router = useRouter()

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
// 筛选条件同步到地址栏：从详情页返回时按 query 恢复，停留在原来的筛选状态。
const filters = reactive({ keyword: '', lamp_type: '', status: '' })

function syncQuery() {
  const query: Record<string, string> = {}
  if (filters.keyword) query.keyword = filters.keyword
  if (filters.lamp_type) query.lamp_type = filters.lamp_type
  if (filters.status) query.status = filters.status
  void router.replace({ query })
}

function applyFilters() {
  syncQuery()
  void reload()
}

function resetFilters() {
  filters.keyword = ''
  filters.lamp_type = ''
  filters.status = ''
  applyFilters()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '照明设施登记入口尚未接入审批流'
}

function openDetail(row: Row) {
  void router.push({ name: 'light-detail', params: { id: row.id } })
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
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
  if (filters.keyword) params.set('keyword', filters.keyword)
  if (filters.lamp_type) params.set('lamp_type', filters.lamp_type)
  if (filters.status) params.set('status', filters.status)
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

onMounted(() => {
  filters.keyword = String(route.query.keyword ?? '')
  filters.lamp_type = String(route.query.lamp_type ?? '')
  filters.status = String(route.query.status ?? '')
  void reload()
})
</script>
