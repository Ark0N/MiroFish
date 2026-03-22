<template>
  <WorkflowLayout
    :stepNum="2"
    stepName="环境搭建"
    :statusClass="statusClass"
    :statusText="statusText"
    :graphData="graphData"
    :graphLoading="graphLoading"
    :currentPhase="2"
    @refresh-graph="refreshGraph"
  >
    <Step2EnvSetup
      :simulationId="currentSimulationId"
      :projectData="projectData"
      :graphData="graphData"
      :systemLogs="systemLogs"
      @go-back="handleGoBack"
      @next-step="handleNextStep"
      @add-log="addLog"
      @update-status="updateStatus"
    />
  </WorkflowLayout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import WorkflowLayout from '../components/WorkflowLayout.vue'
import Step2EnvSetup from '../components/Step2EnvSetup.vue'
import { getProject, getGraphData } from '../api/graph'
import { getSimulation, stopSimulation, getEnvStatus, closeSimulationEnv } from '../api/simulation'

const route = useRoute()
const router = useRouter()

const props = defineProps({
  simulationId: String
})

// Data State
const currentSimulationId = ref(route.params.simulationId)
const projectData = ref(null)
const graphData = ref(null)
const graphLoading = ref(false)
const systemLogs = ref([])
const currentStatus = ref('processing')

// --- Status Computed ---
const statusClass = computed(() => currentStatus.value)

const statusText = computed(() => {
  if (currentStatus.value === 'error') return 'Error'
  if (currentStatus.value === 'completed') return 'Ready'
  return 'Preparing'
})

// --- Helpers ---
const addLog = (msg) => {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
  systemLogs.value.push({ time, msg })
  if (systemLogs.value.length > 100) {
    systemLogs.value.shift()
  }
}

const updateStatus = (status) => {
  currentStatus.value = status
}

const handleGoBack = () => {
  if (projectData.value?.project_id) {
    router.push({ name: 'Process', params: { projectId: projectData.value.project_id } })
  } else {
    router.push('/')
  }
}

const handleNextStep = (params = {}) => {
  addLog('进入 Step 3: 开始模拟')

  if (params.maxRounds) {
    addLog(`自定义模拟轮数: ${params.maxRounds} 轮`)
  } else {
    addLog('使用自动配置的模拟轮数')
  }

  const routeParams = {
    name: 'SimulationRun',
    params: { simulationId: currentSimulationId.value }
  }

  if (params.maxRounds) {
    routeParams.query = { maxRounds: params.maxRounds }
  }

  router.push(routeParams)
}

// --- Data Logic ---

const checkAndStopRunningSimulation = async () => {
  if (!currentSimulationId.value) return

  try {
    const envStatusRes = await getEnvStatus({ simulation_id: currentSimulationId.value })

    if (envStatusRes.success && envStatusRes.data?.env_alive) {
      addLog('检测到模拟环境正在运行，正在关闭...')

      try {
        const closeRes = await closeSimulationEnv({
          simulation_id: currentSimulationId.value,
          timeout: 10
        })

        if (closeRes.success) {
          addLog('模拟环境已关闭')
        } else {
          addLog(`关闭模拟环境失败: ${closeRes.error || '未知错误'}`)
          await forceStopSimulation()
        }
      } catch (closeErr) {
        addLog(`关闭模拟环境异常: ${closeErr.message}`)
        await forceStopSimulation()
      }
    } else {
      const simRes = await getSimulation(currentSimulationId.value)
      if (simRes.success && simRes.data?.status === 'running') {
        addLog('检测到模拟状态为运行中，正在停止...')
        await forceStopSimulation()
      }
    }
  } catch (err) {
    console.warn('检查模拟状态失败:', err)
  }
}

const forceStopSimulation = async () => {
  try {
    const stopRes = await stopSimulation({ simulation_id: currentSimulationId.value })
    if (stopRes.success) {
      addLog('模拟已强制停止')
    } else {
      addLog(`强制停止模拟失败: ${stopRes.error || '未知错误'}`)
    }
  } catch (err) {
    addLog(`强制停止模拟异常: ${err.message}`)
  }
}

const loadSimulationData = async () => {
  try {
    addLog(`加载模拟数据: ${currentSimulationId.value}`)

    const simRes = await getSimulation(currentSimulationId.value)
    if (simRes.success && simRes.data) {
      const simData = simRes.data

      if (simData.project_id) {
        const projRes = await getProject(simData.project_id)
        if (projRes.success && projRes.data) {
          projectData.value = projRes.data
          addLog(`项目加载成功: ${projRes.data.project_id}`)

          if (projRes.data.graph_id) {
            await loadGraph(projRes.data.graph_id)
          }
        }
      }
    } else {
      addLog(`加载模拟数据失败: ${simRes.error || '未知错误'}`)
    }
  } catch (err) {
    addLog(`加载异常: ${err.message}`)
  }
}

const loadGraph = async (graphId) => {
  graphLoading.value = true
  try {
    const res = await getGraphData(graphId)
    if (res.success) {
      graphData.value = res.data
      addLog('图谱数据加载成功')
    }
  } catch (err) {
    addLog(`图谱加载失败: ${err.message}`)
  } finally {
    graphLoading.value = false
  }
}

const refreshGraph = () => {
  if (projectData.value?.graph_id) {
    loadGraph(projectData.value.graph_id)
  }
}

onMounted(async () => {
  addLog('SimulationView 初始化')
  await checkAndStopRunningSimulation()
  loadSimulationData()
})
</script>
