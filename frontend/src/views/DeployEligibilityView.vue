<template>
  <section class="page" data-module="deploy-eligibility">
    <header class="page-head">
      <div>
        <h2>策略下发详情 · 发布资格</h2>
        <p class="page-desc">
          发起发布资格请求后，服务端按整改销项单校验每张策略单关联资源是否重新具备发布资格：
          当前仍打开的风险为阻塞项，已关闭项保留销项单作为历史依据。
        </p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/rectify">前往整改复核页</RouterLink>
      </div>
    </header>

    <table class="data-table">
      <thead>
        <tr>
          <th>分发编号</th><th>策略内容</th><th>目标节点</th><th>关联资源</th>
          <th>当前状态</th><th>发布资格请求</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in policies" :key="String(row.id)" :data-status="String(row.status)">
          <td>{{ row['分发编号'] }}</td>
          <td>{{ row['策略内容'] }}</td>
          <td>{{ row['目标节点'] }}</td>
          <td>{{ row['关联资源'] || '—' }}</td>
          <td><span class="badge" :class="row.status === '待下发' ? 'badge-warn' : 'badge-ok'">{{ row.status }}</span></td>
          <td class="row-actions">
            <button
              class="link"
              type="button"
              :data-testid="`check-${row.id}`"
              @click="checkEligibility(Number(row.id))"
            >
              发起发布资格请求
            </button>
          </td>
        </tr>
        <tr v-if="!policies.length">
          <td colspan="6" class="empty-state">暂无策略分发记录</td>
        </tr>
      </tbody>
    </table>

    <div v-if="verdict" class="verdict-panel" data-testid="verdict-panel">
      <header class="verdict-head">
        <div>
          <h3>{{ verdict.分发编号 }} · 发布资格结论</h3>
          <p class="page-desc">{{ verdict.策略内容 }}</p>
        </div>
        <span class="verdict-tag" :class="verdict.eligible ? 'badge-ok' : 'badge-danger'" data-testid="verdict-tag">
          {{ verdict.eligible ? '此次请求获准：可下发' : '此次请求未获准：存在阻塞项' }}
        </span>
      </header>

      <p v-if="verdict.blocking_summary.length" class="error-text">
        阻塞汇总：{{ verdict.blocking_summary.join('；') }}
      </p>
      <p v-else class="info-text">关联资源全部具备发布资格。</p>

      <div v-for="item in verdict.resources" :key="item.resource" class="resource-card">
        <header class="resource-head">
          <strong>资源：{{ item.resource }}</strong>
          <span class="badge" :class="item.eligible ? 'badge-ok' : 'badge-danger'">
            {{ item.eligible ? '具备发布资格' : '发布被阻塞' }}
          </span>
        </header>

        <h4>阻塞项（当前打开风险）</h4>
        <table v-if="item.blockers.length" class="data-table inner-table">
          <thead>
            <tr><th>问题编号</th><th>问题描述</th><th>风险等级</th><th>问题状态</th></tr>
          </thead>
          <tbody>
            <tr v-for="blocker in item.blockers" :key="blocker.问题编号">
              <td>{{ blocker.问题编号 }}</td>
              <td>{{ blocker.问题描述 }}</td>
              <td><span class="badge" :class="blocker.风险等级 === '高' ? 'badge-danger' : 'badge-warn'">{{ blocker.风险等级 }}</span></td>
              <td>{{ blocker.status }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="info-text">无打开风险，资源可发布。</p>

        <h4>已关闭项历史依据（旧问题销项不盖掉新发现）</h4>
        <table v-if="item.closed_history.length" class="data-table inner-table">
          <thead>
            <tr><th>问题编号</th><th>问题描述</th><th>整改销项单号</th></tr>
          </thead>
          <tbody>
            <tr v-for="history in item.closed_history" :key="history.问题编号">
              <td>{{ history.问题编号 }}</td>
              <td>{{ history.问题描述 }}</td>
              <td>{{ history.销项单号 }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="cell-sub">暂无已关闭历史项。</p>
      </div>

      <div class="page-actions">
        <button
          class="btn primary"
          data-testid="deploy-with-guard"
          type="button"
          :disabled="!verdict.eligible || deploying"
          @click="deploy"
        >
          {{ deploying ? '下发中…' : '按资格结论执行下发策略' }}
        </button>
        <span v-if="!verdict.eligible" class="cell-sub">存在阻塞项时按钮禁用；服务端动作接口同样会拦截。</span>
      </div>
      <footer class="page-foot">
        <span v-if="actionMessage" :class="actionOk ? 'info-text' : 'error-text'">{{ actionMessage }}</span>
      </footer>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { listEntries, runAction } from '@/api/backend-service'
import { fetchPolicyEligibility, type EligibilityVerdict } from '@/api/rectify'
import type { EntryRow } from '@/data/types'

const policies = ref<EntryRow[]>([])
const verdict = ref<EligibilityVerdict | null>(null)
const deploying = ref(false)
const actionMessage = ref('')
const actionOk = ref(false)
const errorMessage = ref('')

async function reloadPolicies() {
  errorMessage.value = ''
  try {
    const payload = await listEntries('deploy_policy')
    policies.value = payload.items
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '策略列表读取失败'
  }
}

async function checkEligibility(policyId: number) {
  actionMessage.value = ''
  errorMessage.value = ''
  try {
    verdict.value = await fetchPolicyEligibility(policyId)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '发布资格请求失败'
  }
}

async function deploy() {
  if (!verdict.value) return
  deploying.value = true
  actionMessage.value = ''
  try {
    const result = await runAction('deploy_policy', verdict.value.policy_id, '下发策略')
    actionOk.value = result.ok
    actionMessage.value = result.message
    if (result.ok) {
      await reloadPolicies()
      await checkEligibility(verdict.value.policy_id)
    }
  } catch (error) {
    actionOk.value = false
    actionMessage.value = error instanceof Error ? error.message : '下发失败'
  } finally {
    deploying.value = false
  }
}

onMounted(reloadPolicies)
</script>
