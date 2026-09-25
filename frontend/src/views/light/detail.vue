<template>
  <section class="page" data-module="light-detail">
    <header class="page-head">
      <div>
        <h2>照明设施详情</h2>
        <p class="page-desc">灯杆 {{ entry?.['灯杆编号'] ?? entryId }} 的台账信息与巡检留档，最近一次巡检与台账列表保持一致。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="goBack">返回列表</button>
      </div>
    </header>

    <p v-if="loadError" class="error-text">{{ loadError }}</p>

    <template v-if="entry">
      <section class="panel">
        <h3 class="panel-title">台账信息</h3>
        <table class="data-table">
          <tbody>
            <tr v-for="column in columns" :key="column">
              <th class="detail-label">{{ column }}</th>
              <td>{{ entry[column] ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="panel">
        <h3 class="panel-title">最近一次巡检</h3>
        <p v-if="!latest" class="empty-state">暂无巡检记录，在下方提交第一条巡检记录后，这里与台账列表会同步展示。</p>
        <table v-else class="data-table">
          <tbody>
            <tr v-for="field in inspectionFields" :key="field.key">
              <th class="detail-label">{{ field.label }}</th>
              <td>{{ latest[field.key] ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="panel">
        <h3 class="panel-title">提交巡检记录</h3>
        <form class="filter-bar" @submit.prevent="submitInspection">
          <label v-for="field in inspectionFields" :key="field.key" class="filter-item">
            <span>{{ field.label }}</span>
            <input v-model="form[field.key]" :type="field.type" :placeholder="`请输入${field.label}`" />
          </label>
          <button class="btn primary" type="submit">保存巡检记录</button>
        </form>
        <p v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</p>
        <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
      </section>

      <section class="panel">
        <h3 class="panel-title">巡检记录留档</h3>
        <table class="data-table">
          <thead>
            <tr>
              <th v-for="field in inspectionFields" :key="field.key">{{ field.label }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in inspections" :key="String(record.id)">
              <td v-for="field in inspectionFields" :key="field.key">{{ record[field.key] ?? '—' }}</td>
            </tr>
            <tr v-if="!inspections.length">
              <td :colspan="inspectionFields.length" class="empty-state">暂无巡检记录，提交后在此留档，同一天重复提交只保留最新一条</td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, any>

const ENDPOINT = '/api/light'
const columns = ["设施编号", "灯杆编号", "灯具类型", "所在道路", "亮灯率", "上次检修日", "责任班组", "设施状态"]
const inspectionFields = [
  { key: '巡检日期', label: '巡检日期', type: 'date' },
  { key: '灯具类型', label: '灯具类型', type: 'text' },
  { key: '上次更换时间', label: '上次更换时间', type: 'date' },
  { key: '本次结论', label: '本次结论', type: 'text' },
]

const route = useRoute()
const router = useRouter()
const entryId = Number(route.params.id)

const entry = ref<Row | null>(null)
const inspections = ref<Row[]>([])
const loadError = ref('')
const errorMessage = ref('')
const noticeMessage = ref('')

const today = new Date().toISOString().slice(0, 10)
const form = ref<Record<string, string>>({ 巡检日期: today })

// 与台账共用同一份后端汇总，保证两边看到的最近一次巡检一致
const latest = computed<Row | null>(() => entry.value?.['最近巡检'] ?? null)

function goBack() {
  // 优先回到来源列表（保留筛选与滚动位置），直接打开详情时回退到列表首页
  if (window.history.state?.back) {
    router.back()
  } else {
    router.push({ path: '/light', query: route.query })
  }
}

async function load() {
  loadError.value = ''
  try {
    const response = await request(`${ENDPOINT}/${entryId}`)
    if (!response.ok) {
      const payload = await response.json().catch(() => null)
      throw new Error(payload?.detail ?? '照明设施详情读取失败')
    }
    const payload = await response.json()
    entry.value = payload
    inspections.value = payload.inspections ?? []
    if (!form.value['灯具类型'] && payload['灯具类型']) {
      form.value['灯具类型'] = String(payload['灯具类型'])
    }
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '照明设施详情读取失败'
  }
}

async function submitInspection() {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${entryId}/inspections`, {
      method: 'POST',
      body: JSON.stringify({ values: form.value }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      errorMessage.value = payload.message ?? '巡检记录保存失败，请检查后重试'
      return
    }
    // 后端会区分“已登记”与“当天已有记录，已更新”，原样提示
    noticeMessage.value = payload.message ?? '巡检记录已登记留档'
    await load()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '巡检记录保存失败'
  }
}

onMounted(load)
</script>

<style scoped>
.panel { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 12px 16px; margin-bottom: 12px; }
.panel-title { margin: 0 0 10px; font-size: 14px; }
.detail-label { width: 140px; color: var(--muted); font-weight: normal; }
.notice-text { color: #067647; font-size: 13px; }
</style>
