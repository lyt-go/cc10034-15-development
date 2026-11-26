<template>
  <section class="page" data-module="rectify">
    <header class="page-head">
      <div>
        <h2>整改复核</h2>
        <p class="page-desc">
          整改人对风险问题提交销项，发布人复核复查记录后签发整改销项单；
          复查必须针对待销项的同一资源和同一问题，旧问题关闭不会盖掉同资源的新发现。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" data-testid="open-new-risk" type="button" @click="openNewRisk">
          登记新风险
        </button>
      </div>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">待销项/待处理问题</span>
        <strong class="stat-value">{{ openIssueCount }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">待发布人复核销项单</span>
        <strong class="stat-value">{{ pendingReviewCount }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">已签发销项单</span>
        <strong class="stat-value">{{ signedCount }}</strong>
      </article>
    </div>

    <div class="tab-row">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        type="button"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>资源标识</span>
        <input v-model="filters.resource" data-testid="filter-resource" placeholder="按资源标识检索" />
      </label>
      <label v-if="activeTab === 'issues'" class="filter-item">
        <span>问题状态</span>
        <input v-model="filters.status" data-testid="filter-status" placeholder="待销项/待复核/已关闭/复核驳回" />
      </label>
      <button class="btn" data-testid="query" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <!-- 风险问题 -->
    <table v-if="activeTab === 'issues'" class="data-table">
      <thead>
        <tr>
          <th>问题编号</th><th>资源标识</th><th>问题描述</th><th>风险等级</th>
          <th>当前状态</th><th>整改责任人</th><th>整改说明</th><th>销项单号/历史依据</th><th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in issues" :key="String(row.id)" :data-status="row.status">
          <td>{{ row.问题编号 }}</td>
          <td>{{ row.资源标识 }}</td>
          <td>{{ row.问题描述 }}</td>
          <td><span class="badge" :class="levelClass(row.风险等级)">{{ row.风险等级 }}</span></td>
          <td><span class="badge" :class="statusClass(row.status)">{{ row.status }}</span></td>
          <td>{{ row.整改责任人 }}</td>
          <td class="cell-note">{{ row.整改说明 || '—' }}</td>
          <td>
            <div>当前：{{ row.销项单号 || '—' }}</div>
            <div v-if="row.关联历史销项单" class="cell-sub">历史销项单：{{ row.关联历史销项单 }}（不盖掉新发现）</div>
          </td>
          <td class="row-actions">
            <button
              v-if="row.status === '待销项' || row.status === '复核驳回'"
              class="link"
              type="button"
              :data-testid="`submit-closure-${row.id}`"
              @click="openClosure(row)"
            >
              提交销项
            </button>
            <span v-else class="cell-sub">{{ row.status === '待复核' ? '等待发布人复核' : '已闭环' }}</span>
          </td>
        </tr>
        <tr v-if="!issues.length">
          <td colspan="9" class="empty-state">暂无符合条件的风险问题</td>
        </tr>
      </tbody>
    </table>

    <!-- 整改销项单 -->
    <table v-else class="data-table">
      <thead>
        <tr>
          <th>销项单号</th><th>问题编号</th><th>资源标识</th><th>问题描述</th>
          <th>单据状态</th><th>整改人/整改说明</th><th>复核人/复查记录</th><th>服务端校验依据</th><th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in reviews" :key="String(row.id)" :data-status="row.status">
          <td>{{ row.销项单号 }}</td>
          <td>{{ row.问题编号 }}</td>
          <td>{{ row.资源标识 }}</td>
          <td>{{ row.问题描述 }}</td>
          <td><span class="badge" :class="statusClass(row.status)">{{ row.status }}</span></td>
          <td>
            <div>{{ row.整改责任人 }}</div>
            <div class="cell-sub">{{ row.整改说明 }}</div>
          </td>
          <td>
            <div>{{ row.复核人 || '待复核' }}</div>
            <div class="cell-sub">{{ row.复查记录 || '—' }}</div>
          </td>
          <td class="cell-note">{{ row.校验依据 || '待复核后签发' }}</td>
          <td class="row-actions">
            <button
              v-if="row.status === '待复核'"
              class="link"
              type="button"
              :data-testid="`open-review-${row.id}`"
              @click="openReview(row)"
            >
              发布人复核
            </button>
            <span v-else class="cell-sub">{{ row.签发时间 || '已驳回' }}</span>
          </td>
        </tr>
        <tr v-if="!reviews.length">
          <td colspan="9" class="empty-state">暂无整改销项单</td>
        </tr>
      </tbody>
    </table>

    <!-- 提交销项弹窗 -->
    <div v-if="closureTarget" class="modal-backdrop" data-testid="closure-modal">
      <form class="modal" @submit.prevent="confirmClosure">
        <h3>提交整改销项 · {{ closureTarget.问题编号 }}</h3>
        <dl class="detail-grid">
          <dt>资源标识</dt><dd>{{ closureTarget.资源标识 }}</dd>
          <dt>问题描述</dt><dd>{{ closureTarget.问题描述 }}</dd>
        </dl>
        <p class="cell-sub">销项将绑定同一资源标识与同一问题描述，提交后由发布人复核签发。</p>
        <label class="create-field">
          <span>整改说明（必填）</span>
          <textarea v-model="closureNote" data-testid="closure-note" rows="4" required />
        </label>
        <div class="page-actions">
          <button class="btn" type="button" @click="closureTarget = null">取消</button>
          <button class="btn primary" data-testid="confirm-closure" type="submit" :disabled="submitting">
            {{ submitting ? '提交中…' : '提交销项' }}
          </button>
        </div>
      </form>
    </div>

    <!-- 发布人复核弹窗 -->
    <div v-if="reviewTarget" class="modal-backdrop" data-testid="review-modal">
      <form class="modal" @submit.prevent="confirmReview(true)">
        <h3>发布人复核 · {{ reviewTarget.销项单号 }}</h3>
        <dl class="detail-grid">
          <dt>原风险问题</dt><dd>{{ reviewTarget.问题编号 }}（来源扫描 {{ reviewTarget.来源扫描任务 }}）</dd>
          <dt>资源标识</dt><dd>{{ reviewTarget.资源标识 }}</dd>
          <dt>问题描述</dt><dd>{{ reviewTarget.问题描述 }}</dd>
          <dt>整改说明</dt><dd>{{ reviewTarget.整改说明 }}</dd>
        </dl>
        <label class="create-field">
          <span>复核人（发布人，必填）</span>
          <input v-model="reviewForm.reviewer" data-testid="review-reviewer" required />
        </label>
        <label class="create-field">
          <span>复查记录（必填，服务端据此校验原风险与复查是否同一资源同一问题）</span>
          <textarea v-model="reviewForm.recheck_note" data-testid="review-note" rows="4" required />
        </label>
        <label class="create-field">
          <span>复核意见</span>
          <input v-model="reviewForm.opinion" data-testid="review-opinion" />
        </label>
        <div class="page-actions">
          <button class="btn" type="button" @click="reviewTarget = null">取消</button>
          <button
            class="btn danger"
            data-testid="review-reject"
            type="button"
            :disabled="submitting"
            @click="confirmReview(false)"
          >
            驳回整改
          </button>
          <button class="btn primary" data-testid="review-approve" type="submit" :disabled="submitting">
            {{ submitting ? '提交中…' : '复核通过并签发' }}
          </button>
        </div>
      </form>
    </div>

    <!-- 新风险登记弹窗 -->
    <div v-if="showNewRisk" class="modal-backdrop" data-testid="new-risk-modal">
      <form class="modal" @submit.prevent="confirmNewRisk">
        <h3>登记同资源新风险</h3>
        <p class="cell-sub">
          新风险会独立成单并阻塞发布；若该资源同问题曾有已签发销项单，仅作为历史依据回链，不会盖掉本次发现。
        </p>
        <label class="create-field">
          <span>资源标识（必填）</span>
          <input v-model="newRisk.resource" data-testid="new-risk-resource" required />
        </label>
        <label class="create-field">
          <span>问题描述（必填）</span>
          <textarea v-model="newRisk.problem" data-testid="new-risk-problem" rows="3" required />
        </label>
        <label class="create-field">
          <span>风险等级</span>
          <input v-model="newRisk.level" data-testid="new-risk-level" placeholder="高/中/低" />
        </label>
        <label class="create-field">
          <span>来源扫描任务</span>
          <input v-model="newRisk.source_task" data-testid="new-risk-task" placeholder="如 RISK-0010" />
        </label>
        <label class="create-field">
          <span>整改责任人</span>
          <input v-model="newRisk.owner" data-testid="new-risk-owner" />
        </label>
        <div class="page-actions">
          <button class="btn" type="button" @click="showNewRisk = false">取消</button>
          <button class="btn primary" data-testid="confirm-new-risk" type="submit" :disabled="submitting">
            {{ submitting ? '提交中…' : '确认登记' }}
          </button>
        </div>
      </form>
    </div>

    <footer class="page-foot">
      <span>风险问题 {{ issues.length }} 条 · 销项单 {{ reviews.length }} 张</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-else-if="infoMessage" class="info-text">{{ infoMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  decideReview,
  listRectifyReviews,
  listRiskIssues,
  registerNewRisk,
  submitClosure,
  type RectifyReview,
  type RiskIssue,
} from '@/api/rectify'

const tabs = [
  { key: 'issues', label: '风险问题与销项提交' },
  { key: 'reviews', label: '整改销项单与发布人复核' },
] as const

const activeTab = ref<(typeof tabs)[number]['key']>('issues')
const issues = ref<RiskIssue[]>([])
const reviews = ref<RectifyReview[]>([])
const filters = ref<Record<string, string>>({ resource: '', status: '' })
const errorMessage = ref('')
const infoMessage = ref('')
const submitting = ref(false)

const closureTarget = ref<RiskIssue | null>(null)
const closureNote = ref('')
const reviewTarget = ref<RectifyReview | null>(null)
const reviewForm = ref({ reviewer: '', recheck_note: '', opinion: '' })
const showNewRisk = ref(false)
const newRisk = ref({ resource: '', problem: '', level: '中', source_task: '', owner: '' })

const openIssueCount = computed(
  () => issues.value.filter((row) => row.status !== '已关闭').length,
)
const pendingReviewCount = computed(
  () => reviews.value.filter((row) => row.status === '待复核').length,
)
const signedCount = computed(
  () => reviews.value.filter((row) => row.status === '已签发').length,
)

function statusClass(status: string): string {
  if (status === '已关闭' || status === '已签发') return 'badge-ok'
  if (status === '复核驳回' || status === '已驳回') return 'badge-danger'
  return 'badge-warn'
}

function levelClass(level: string): string {
  if (level === '高') return 'badge-danger'
  if (level === '低') return 'badge-ok'
  return 'badge-warn'
}

function resetFilters() {
  filters.value = { resource: '', status: '' }
  void reload()
}

async function reload() {
  errorMessage.value = ''
  try {
    const issueFilters: Record<string, string> = {}
    if (filters.value.resource.trim()) issueFilters.resource = filters.value.resource.trim()
    if (activeTab.value === 'issues' && filters.value.status.trim()) {
      issueFilters.status = filters.value.status.trim()
    }
    const [issueRows, reviewRows] = await Promise.all([
      listRiskIssues(issueFilters),
      listRectifyReviews(),
    ])
    issues.value = issueRows
    reviews.value = reviewRows
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '整改复核数据读取失败'
  }
}

function openClosure(row: RiskIssue) {
  closureTarget.value = row
  closureNote.value = row.整改说明 || ''
  errorMessage.value = ''
  infoMessage.value = ''
}

async function confirmClosure() {
  if (!closureTarget.value) return
  submitting.value = true
  errorMessage.value = ''
  try {
    const result = await submitClosure(closureTarget.value.id, closureNote.value)
    if (!result.ok) throw new Error(result.message)
    infoMessage.value = result.message
    closureTarget.value = null
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '销项提交失败'
  } finally {
    submitting.value = false
  }
}

function openReview(row: RectifyReview) {
  reviewTarget.value = row
  reviewForm.value = { reviewer: '', recheck_note: '', opinion: '' }
  errorMessage.value = ''
  infoMessage.value = ''
}

async function confirmReview(approve: boolean) {
  if (!reviewTarget.value) return
  if (!reviewForm.value.reviewer.trim() || !reviewForm.value.recheck_note.trim()) {
    errorMessage.value = '复核人与复查记录均为必填'
    return
  }
  submitting.value = true
  errorMessage.value = ''
  try {
    const result = await decideReview(reviewTarget.value.id, {
      approve,
      reviewer: reviewForm.value.reviewer.trim(),
      recheck_note: reviewForm.value.recheck_note.trim(),
      opinion: reviewForm.value.opinion.trim(),
    })
    if (!result.ok) throw new Error(result.message)
    infoMessage.value = result.message
    reviewTarget.value = null
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '复核失败'
  } finally {
    submitting.value = false
  }
}

function openNewRisk() {
  newRisk.value = { resource: filters.value.resource || '', problem: '', level: '中', source_task: '', owner: '' }
  showNewRisk.value = true
  errorMessage.value = ''
  infoMessage.value = ''
}

async function confirmNewRisk() {
  submitting.value = true
  errorMessage.value = ''
  try {
    const result = await registerNewRisk({
      resource: newRisk.value.resource.trim(),
      problem: newRisk.value.problem.trim(),
      level: newRisk.value.level.trim() || '中',
      source_task: newRisk.value.source_task.trim(),
      owner: newRisk.value.owner.trim(),
    })
    if (!result.ok) throw new Error(result.message)
    infoMessage.value = result.message
    showNewRisk.value = false
    activeTab.value = 'issues'
    filters.value = { resource: newRisk.value.resource.trim(), status: '' }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '新风险登记失败'
  } finally {
    submitting.value = false
  }
}

onMounted(reload)
</script>
