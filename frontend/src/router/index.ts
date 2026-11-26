import { createRouter, createWebHistory } from 'vue-router'

import DeployEligibilityView from '@/views/DeployEligibilityView.vue'
import Overview from '@/views/Overview.vue'
import RectifyView from '@/views/RectifyView.vue'
import WorkbenchView from '@/views/WorkbenchView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'overview', component: Overview },
    // 整改复核是跨风险扫描/策略下发的专项流程页，需先于动态模块路由注册
    { path: '/rectify', name: 'rectify', component: RectifyView },
    { path: '/deploy-eligibility', name: 'deploy-eligibility', component: DeployEligibilityView },
    { path: '/:moduleKey', name: 'module', component: WorkbenchView, props: true },
  ],
})

export default router
