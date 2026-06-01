import { useEffect, useRef } from 'react'
import {
  Clock, CheckCircle2, XCircle, Loader2, Eye, Trash2, AlertCircle,
} from 'lucide-react'
import { watchJob, deleteJob } from '../api/client'

const STATUS_META = {
  queued:    { label: 'Na fila',   Icon: Clock,        cls: 'badge-queued'    },
  running:   { label: 'Rodando',  Icon: Loader2,      cls: 'badge-running'   },
  completed: { label: 'Concluído', Icon: CheckCircle2, cls: 'badge-completed' },
  failed:    { label: 'Falhou',    Icon: XCircle,      cls: 'badge-failed'    },
}

function Badge({ status }) {
  const { label, Icon, cls } = STATUS_META[status] ?? STATUS_META.queued
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      <Icon size={11} className={status === 'running' ? 'animate-spin' : ''} />
      {label}
    </span>
  )
}

function ProgressBar({ value }) {
  return (
    <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full transition-all duration-300 ${
          value < 100 ? 'bg-brand-500' : 'bg-emerald-500'
        }`}
        style={{ width: `${value}%` }}
      />
    </div>
  )
}

function elapsed(iso) {
  if (!iso) return null
  const diff = Math.round((Date.now() - new Date(iso).getTime()) / 1000)
  if (diff < 60) return `${diff}s`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ${diff % 60}s`
  return `${Math.floor(diff / 3600)}h`
}

export default function JobCard({ job, onUpdate, onSelect, isSelected }) {
  const wsRef = useRef(null)

  // Connect WebSocket for live updates while job is active
  useEffect(() => {
    if (job.status !== 'queued' && job.status !== 'running') return
    if (wsRef.current) return // already watching

    wsRef.current = watchJob(job.id, {
      onMessage: (msg) => onUpdate(job.id, msg),
      onClose:   () => { wsRef.current = null },
    })

    return () => {
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [job.id, job.status, onUpdate])

  async function handleDelete(e) {
    e.stopPropagation()
    try {
      await deleteJob(job.id)
      onUpdate(job.id, null) // null signals removal
    } catch {
      /* ignore */
    }
  }

  const duration = job.started_at && job.finished_at
    ? elapsed(job.started_at)
    : job.started_at
    ? `rodando há ${elapsed(job.started_at)}`
    : null

  return (
    <div
      className={`card p-3 space-y-2 cursor-pointer transition-colors
        ${isSelected ? 'ring-1 ring-brand-500 bg-slate-800/60' : 'hover:bg-slate-800/40'}`}
      onClick={() => job.status === 'completed' && onSelect(job.id)}
      title={job.status === 'completed' ? 'Clique para visualizar em 3D' : undefined}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-0.5 min-w-0">
          <p className="text-xs font-mono text-slate-500 truncate">{job.id.slice(0, 8)}…</p>
          <Badge status={job.status} />
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {job.status === 'completed' && (
            <button
              className="btn-ghost py-1 px-2 text-brand-400 hover:text-brand-300"
              onClick={(e) => { e.stopPropagation(); onSelect(job.id) }}
            >
              <Eye size={14} />
            </button>
          )}
          <button className="btn-ghost py-1 px-2 text-red-400/60 hover:text-red-400" onClick={handleDelete}>
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {/* Progress */}
      {(job.status === 'running' || job.status === 'completed') && (
        <ProgressBar value={job.progress} />
      )}

      {/* Message */}
      <p className="text-xs text-slate-400 truncate">{job.message}</p>

      {/* Error */}
      {job.status === 'failed' && job.error && (
        <div className="flex gap-1.5 text-xs text-red-400 bg-red-500/10 rounded p-2">
          <AlertCircle size={12} className="shrink-0 mt-0.5" />
          <span className="line-clamp-3 font-mono">{job.error.split('\n').pop()}</span>
        </div>
      )}

      {/* Duration */}
      {duration && (
        <p className="text-xs text-slate-600 flex items-center gap-1">
          <Clock size={10} />
          {duration}
        </p>
      )}

      {/* Params summary */}
      <div className="flex flex-wrap gap-1">
        {job.params?.mode && (
          <span className="text-[10px] bg-slate-800 text-slate-500 px-1.5 py-0.5 rounded">
            {job.params.mode}
          </span>
        )}
        {job.params?.mask_sky && (
          <span className="text-[10px] bg-slate-800 text-slate-500 px-1.5 py-0.5 rounded">
            sky-mask
          </span>
        )}
        {job.params?.keyframe_interval > 1 && (
          <span className="text-[10px] bg-slate-800 text-slate-500 px-1.5 py-0.5 rounded">
            kf={job.params.keyframe_interval}
          </span>
        )}
      </div>
    </div>
  )
}
