<template>
  <WorkflowLayout
    :stepNum="4"
    stepName="Report Generation"
    :statusClass="statusClass"
    :statusText="statusText"
    :graphData="graphData"
    :graphLoading="graphLoading"
    :currentPhase="4"
    initialViewMode="workbench"
    @refresh-graph="refreshGraph"
  >
    <Step4Report
      :reportId="currentReportId"
      :simulationId="simulationId"
      :systemLogs="systemLogs"
      @add-log="addLog"
      @update-status="updateStatus"
    />
  </WorkflowLayout>
</template>

<script setup>
import { ref, computed, onMounted, watch, defineAsyncComponent } from 'vue'
import { useRoute } from 'vue-router'
import WorkflowLayout from '../components/WorkflowLayout.vue'
const Step4Report = defineAsyncComponent(() => import('../components/Step4Report.vue'))
import { getProject, getGraphData } from '../api/graph'
import { getSimulation } from '../api/simulation'
import { getReport } from '../api/report'
import { useSystemLog } from '../composables/useSystemLog'

const route = useRoute()

const props = defineProps({
  reportId: String
})

// Data State
const currentReportId = ref(route.params.reportId)
const simulationId = ref(null)
const projectData = ref(null)
const graphData = ref(null)
const graphLoading = ref(false)
const { systemLogs, addLog } = useSystemLog(200)
const currentStatus = ref('processing')

// --- Status Computed ---
const statusClass = computed(() => currentStatus.value)

const statusText = computed(() => {
  if (currentStatus.value === 'error') return 'Error'
  if (currentStatus.value === 'completed') return 'Completed'
  return 'Generating'
})

// --- Helpers ---
const updateStatus = (status) => {
  currentStatus.value = status
}

// --- Data Logic ---
const loadReportData = async () => {
  try {
    addLog(`Loading report data: ${currentReportId.value}`)

    const reportRes = await getReport(currentReportId.value)
    if (reportRes.success && reportRes.data) {
      const reportData = reportRes.data
      simulationId.value = reportData.simulation_id

      if (simulationId.value) {
        const simRes = await getSimulation(simulationId.value)
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
        }
      }
    } else {
      addLog(`Failed to get report info: ${reportRes.error || 'Unknown error'}`)
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
    addLog(`Graph loading failed: ${err.message}`)
  } finally {
    graphLoading.value = false
  }
}

const refreshGraph = () => {
  if (projectData.value?.graph_id) {
    loadGraph(projectData.value.graph_id)
  }
}

watch(() => route.params.reportId, (newId) => {
  if (newId) {
    currentReportId.value = newId
    loadReportData()
  }
}, { immediate: true })

onMounted(() => {
  addLog('ReportView initialized')
})
</script>
