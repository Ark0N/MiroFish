<template>
  <WorkflowLayout
    :stepNum="2"
    stepName="Environment Setup"
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
import { useSystemLog } from '../composables/useSystemLog'

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
const { systemLogs, addLog } = useSystemLog(100)
const currentStatus = ref('processing')

// --- Status Computed ---
const statusClass = computed(() => currentStatus.value)

const statusText = computed(() => {
  if (currentStatus.value === 'error') return 'Error'
  if (currentStatus.value === 'completed') return 'Ready'
  return 'Preparing'
})

// --- Helpers ---
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
  addLog('Entering Step 3: Start Simulation')

  if (params.maxRounds) {
    addLog(`Custom simulation rounds: ${params.maxRounds}`)
  } else {
    addLog('Using auto-configured simulation rounds')
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
      addLog('Detected running simulation environment, shutting down...')

      try {
        const closeRes = await closeSimulationEnv({
          simulation_id: currentSimulationId.value,
          timeout: 10
        })

        if (closeRes.success) {
          addLog('Simulation environment closed')
        } else {
          addLog(`Failed to close simulation environment: ${closeRes.error || 'Unknown error'}`)
          await forceStopSimulation()
        }
      } catch (closeErr) {
        addLog(`Error closing simulation environment: ${closeErr.message}`)
        await forceStopSimulation()
      }
    } else {
      const simRes = await getSimulation(currentSimulationId.value)
      if (simRes.success && simRes.data?.status === 'running') {
        addLog('Detected simulation is running, stopping...')
        await forceStopSimulation()
      }
    }
  } catch (err) {
    addLog('Failed to check simulation status')
  }
}

const forceStopSimulation = async () => {
  try {
    const stopRes = await stopSimulation({ simulation_id: currentSimulationId.value })
    if (stopRes.success) {
      addLog('Simulation force stopped')
    } else {
      addLog(`Failed to force stop simulation: ${stopRes.error || 'Unknown error'}`)
    }
  } catch (err) {
    addLog(`Error force stopping simulation: ${err.message}`)
  }
}

const loadSimulationData = async () => {
  try {
    addLog(`Loading simulation data: ${currentSimulationId.value}`)

    const simRes = await getSimulation(currentSimulationId.value)
    if (simRes.success && simRes.data) {
      const simData = simRes.data

      if (simData.project_id) {
        const projRes = await getProject(simData.project_id)
        if (projRes.success && projRes.data) {
          projectData.value = projRes.data
          addLog(`Project loaded successfully: ${projRes.data.project_id}`)

          if (projRes.data.graph_id) {
            await loadGraph(projRes.data.graph_id)
          }
        }
      }
    } else {
      addLog(`Failed to load simulation data: ${simRes.error || 'Unknown error'}`)
    }
  } catch (err) {
    addLog(`Loading error: ${err.message}`)
  }
}

const loadGraph = async (graphId) => {
  graphLoading.value = true
  try {
    const res = await getGraphData(graphId)
    if (res.success) {
      graphData.value = res.data
      addLog('Graph data loaded successfully')
    }
  } catch (err) {
    addLog(`Failed to load graph: ${err.message}`)
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
  addLog('SimulationView initialized')
  await checkAndStopRunningSimulation()
  loadSimulationData()
})
</script>
