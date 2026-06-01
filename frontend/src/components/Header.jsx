import { Box, Activity, Github } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getHealth } from '../api/client'

export default function Header() {
  const [health, setHealth] = useState(null)

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null))

    const id = setInterval(() => {
      getHealth().then(setHealth).catch(() => setHealth(null))
    }, 15_000)
    return () => clearInterval(id)
  }, [])

  return (
    <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-screen-2xl mx-auto px-4 h-14 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-2.5">
          <Box className="text-brand-500" size={22} />
          <span className="font-semibold text-base tracking-tight">LingBot-Map</span>
          <span className="hidden sm:block text-xs text-slate-500 mt-0.5">
            Reconstrução 3D em Streaming
          </span>
        </div>

        {/* Status pill */}
        <div className="flex items-center gap-3">
          {health ? (
            <div className="flex items-center gap-1.5 text-xs">
              <span
                className={`w-2 h-2 rounded-full ${
                  health.model_loaded ? 'bg-emerald-400' : 'bg-amber-400'
                }`}
              />
              <span className="text-slate-400 hidden sm:block">
                {health.model_loaded
                  ? `Modelo pronto · ${health.gpu?.name ?? 'CPU'}`
                  : 'Aguardando modelo…'}
              </span>
              {health.gpu?.memory_allocated_gb != null && (
                <span className="text-slate-600 hidden md:block">
                  · VRAM {health.gpu.memory_allocated_gb} GB
                </span>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-xs text-slate-600">
              <Activity size={14} />
              <span>Conectando…</span>
            </div>
          )}

          <a
            href="https://github.com/robbyant/lingbot-map"
            target="_blank"
            rel="noreferrer"
            className="btn-ghost"
            aria-label="GitHub"
          >
            <Github size={16} />
          </a>
        </div>
      </div>
    </header>
  )
}
