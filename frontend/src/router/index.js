import { createRouter, createWebHistory } from 'vue-router'

const Home = () => import('../views/Home.vue')
const Process = () => import('../views/MainView.vue')
const SimulationView = () => import('../views/SimulationView.vue')
const SimulationRunView = () => import('../views/SimulationRunView.vue')
const ReportView = () => import('../views/ReportView.vue')
const InteractionView = () => import('../views/InteractionView.vue')

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/process/:projectId',
    name: 'Process',
    component: Process,
    props: true
  },
  {
    path: '/simulation/:simulationId',
    name: 'Simulation',
    component: SimulationView,
    props: true
  },
  {
    path: '/simulation/:simulationId/start',
    name: 'SimulationRun',
    component: SimulationRunView,
    props: true
  },
  {
    path: '/report/:reportId',
    name: 'Report',
    component: ReportView,
    props: true
  },
  {
    path: '/interaction/:reportId',
    name: 'Interaction',
    component: InteractionView,
    props: true
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('../views/NotFound.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  // Always allow home and 404
  if (to.name === 'Home' || to.name === 'NotFound') {
    return next()
  }

  // Check required params exist
  const requiredParams = {
    'Process': 'projectId',
    'Simulation': 'simulationId',
    'SimulationRun': 'simulationId',
    'Report': 'reportId',
    'Interaction': 'reportId'
  }

  const paramName = requiredParams[to.name]
  if (paramName && !to.params[paramName]) {
    return next({ name: 'Home' })
  }

  next()
})

export default router
