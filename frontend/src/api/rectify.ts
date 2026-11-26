import { request } from './client'

export type RiskIssue = {
  id: number
  status: string
  pending: boolean
  abnormal: boolean
  问题编号: string
  关联任务: string
  资源标识: string
  问题描述: string
  风险等级: string
  发现时间: string
  整改责任人: string
  整改说明: string
  提交时间: string
  销项单号: string
  关联历史销项单: string
}

export type RectifyReview = {
  id: number
  status: string
  pending: boolean
  abnormal: boolean
  销项单号: string
  问题编号: string
  资源标识: string
  问题描述: string
  来源扫描任务: string
  整改责任人: string
  整改说明: string
  提交时间: string
  复核人: string
  复查记录: string
  复核意见: string
  签发时间: string
  校验依据: string
}

export type EligibilityResource = {
  resource: string
  eligible: boolean
  blockers: { 问题编号: string; 问题描述: string; 风险等级: string; status: string }[]
  closed_history: { 问题编号: string; 问题描述: string; 销项单号: string }[]
}

export type EligibilityVerdict = {
  policy_id: number
  分发编号: string
  策略内容: string
  eligible: boolean
  resources: EligibilityResource[]
  blocking_summary: string[]
  message?: string
}

type ListEnvelope<T> = { items: T[]; total: number }
type SimpleResult = { ok: boolean; message: string }

async function readJson<T>(response: Response): Promise<T> {
  return (await response.json()) as T
}

export async function listRiskIssues(filters: Record<string, string> = {}): Promise<RiskIssue[]> {
  const query = new URLSearchParams(filters).toString()
  const response = await request(`/api/rectify/issues?${query}`)
  if (!response.ok) throw new Error('风险问题读取失败')
  const payload = await readJson<ListEnvelope<RiskIssue>>(response)
  return payload.items
}

export async function listRectifyReviews(status = ''): Promise<RectifyReview[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : ''
  const response = await request(`/api/rectify/reviews${query}`)
  if (!response.ok) throw new Error('整改销项单读取失败')
  const payload = await readJson<ListEnvelope<RectifyReview>>(response)
  return payload.items
}

export async function submitClosure(issueId: number, rectifyNote: string): Promise<SimpleResult> {
  const response = await request('/api/rectify/closures', {
    method: 'POST',
    body: JSON.stringify({ issue_id: issueId, rectify_note: rectifyNote }),
  })
  return readJson<SimpleResult>(response)
}

export async function decideReview(
  reviewId: number,
  payload: { approve: boolean; reviewer: string; recheck_note: string; opinion?: string },
): Promise<SimpleResult> {
  const response = await request(`/api/rectify/reviews/${reviewId}/decision`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return readJson<SimpleResult>(response)
}

export async function registerNewRisk(payload: {
  resource: string
  problem: string
  level?: string
  source_task?: string
  owner?: string
}): Promise<SimpleResult> {
  const response = await request('/api/rectify/new-risk', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return readJson<SimpleResult>(response)
}

export async function fetchPolicyEligibility(policyId: number): Promise<EligibilityVerdict> {
  const response = await request(`/api/deploy-policies/${policyId}/eligibility`)
  if (!response.ok) throw new Error('发布资格校验请求失败')
  return readJson<EligibilityVerdict>(response)
}
