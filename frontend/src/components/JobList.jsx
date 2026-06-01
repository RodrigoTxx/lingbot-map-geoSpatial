import { useEffect, useState, useCallback } from 'react'
import { ListChecks, RefreshCw } from 'lucide-react'
import { listJobs } from '../api/client'
import JobCard from './JobCard'

export default function JobList({ jobs, onJobsChange, selectedJobId, onSelect }) {
  const [refreshing, setRefreshing] = useState(false)

  const refresh = useCallback(async () => {
    setRefreshing(true)
    try {
      const data = await listJobs()
      // Rebuild map from server data
      const updated = {}
      for (const j of data) updated[j.id] = j
      onJobsChange(updated)
    } finally {
      setRefreshing(false)
    }
  }, [onJobsChange])

  // Poll every 10 s to catch jobs that might have been missed by WebSocket
  useEffect(() => {
    const id = setInterval(refresh, 10_000)
    return () => clearInterval(id)
  }, [refresh])

  const sortedJobs = Object.values(jobs).sort(
    (a, b) => new Date(b.created_at) - new Date(a.created_at)
  )

  function handleUpdate(jobId, patch) {
    if (patch === null) {
      // Job was deleted
      onJobsChange((prev) => {
        const next = { ...prev }
        delete next[jobId]
        return next
      })
      return
    }
    onJobsChange((prev) => ({
      ...prev,
      [jobId]: { ...(prev[jobId] ?? {}), ...patch },
    }))
  }

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-medium text-slate-300">
          <ListChecks size={16} className="text-brand-500" />
          Jobs ({sortedJobs.length})
        </div>
        <button
          className="btn-ghost py-1"
          onClick={refresh}
          disabled={refreshing}
          title="Atualizar lista"
        >
          <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* List */}
      {sortedJobs.length === 0 ? (
        <div className="text-center py-8 text-sm text-slate-600">
          Nenhum job ainda. Envie imagens ou um vídeo acima.
        </div>
      ) : (
        <div className="space-y-2">
          {sortedJobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              onUpdate={handleUpdate}
              onSelect={onSelect}
              isSelected={job.id === selectedJobId}
            />
          ))}
        </div>
      )}
    </div>
  )
}
