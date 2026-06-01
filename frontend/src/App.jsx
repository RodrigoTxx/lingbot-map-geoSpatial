import { useState, useCallback } from 'react'
import Header from './components/Header'
import UploadPanel from './components/UploadPanel'
import JobList from './components/JobList'
import Viewer3D from './components/Viewer3D'
import { Box } from 'lucide-react'

export default function App() {
  // Map of jobId → job object (source of truth for UI)
  const [jobs, setJobs] = useState({})
  const [selectedJobId, setSelectedJobId] = useState(null)

  const handleJobCreated = useCallback((newJob) => {
    setJobs((prev) => ({ ...prev, [newJob.id]: newJob }))
    // Auto-select when completed later (handled in JobCard via WebSocket)
  }, [])

  const handleJobsChange = useCallback((updater) => {
    setJobs((prev) =>
      typeof updater === 'function' ? updater(prev) : updater
    )
  }, [])

  const handleSelect = useCallback((jobId) => {
    setSelectedJobId((cur) => (cur === jobId ? null : jobId))
  }, [])

  const showViewer = selectedJobId && jobs[selectedJobId]?.status === 'completed'

  return (
    <div className="flex flex-col h-screen">
      <Header />

      <div className="flex flex-1 min-h-0">
        {/* ── Left sidebar ── */}
        <aside className="w-80 xl:w-96 shrink-0 flex flex-col border-r border-slate-800 overflow-y-auto">
          {/* Upload section */}
          <div className="p-4 border-b border-slate-800">
            <h2 className="text-sm font-semibold text-slate-300 mb-3">
              Nova Reconstrução
            </h2>
            <UploadPanel onJobCreated={handleJobCreated} />
          </div>

          {/* Job list */}
          <div className="flex-1 p-4 overflow-y-auto">
            <JobList
              jobs={jobs}
              onJobsChange={handleJobsChange}
              selectedJobId={selectedJobId}
              onSelect={handleSelect}
            />
          </div>
        </aside>

        {/* ── Main canvas ── */}
        <main className="flex-1 min-w-0 p-4">
          {showViewer ? (
            <Viewer3D key={selectedJobId} jobId={selectedJobId} />
          ) : (
            <EmptyState />
          )}
        </main>
      </div>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-4 text-center select-none">
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800">
        <Box size={40} className="text-slate-700" />
      </div>
      <div className="space-y-1">
        <p className="text-slate-400 font-medium">Nenhuma cena selecionada</p>
        <p className="text-sm text-slate-600 max-w-xs">
          Envie imagens ou um vídeo no painel à esquerda e clique em um job
          concluído para visualizar a reconstrução 3D.
        </p>
      </div>
    </div>
  )
}
