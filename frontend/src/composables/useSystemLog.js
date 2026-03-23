import { ref } from 'vue'

export function useSystemLog(maxEntries = 200) {
  const systemLogs = ref([])

  const addLog = (msg) => {
    const time = new Date().toLocaleTimeString('en-US', {
      hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit'
    }) + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
    systemLogs.value.push({ time, msg })
    if (systemLogs.value.length > maxEntries) {
      systemLogs.value.shift()
    }
  }

  return { systemLogs, addLog }
}
