import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '@/pages/LoginView.vue'
import HistoryView from '@/pages/HistoryView.vue'
import JobUploadView from '@/pages/JobUploadView.vue'
import JobTemplateView from '@/pages/JobTemplateView.vue'
import JobDataCheckView from '@/pages/JobDataCheckView.vue'
import JobMappingView from '@/pages/JobMappingView.vue'
import JobNormalizationView from '@/pages/JobNormalizationView.vue'
import JobResultView from '@/pages/JobResultView.vue'
import JobDetailView from '@/pages/JobDetailView.vue'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: LoginView,
  },
  {
    path: '/',
    name: 'history',
    component: HistoryView,
  },
  {
    path: '/jobs/new',
    name: 'job-upload',
    component: JobUploadView,
  },
  {
    path: '/jobs/:id/template',
    name: 'job-template',
    component: JobTemplateView,
  },
  {
    path: '/jobs/:id/data',
    name: 'job-data',
    component: JobDataCheckView,
  },
  {
    path: '/jobs/:id/mapping',
    name: 'job-mapping',
    component: JobMappingView,
  },
  {
    path: '/jobs/:id/normalization',
    name: 'job-normalization',
    component: JobNormalizationView,
  },
  {
    path: '/jobs/:id/result',
    name: 'job-result',
    component: JobResultView,
  },
  {
    path: '/history/:id',
    name: 'job-detail',
    component: JobDetailView,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
