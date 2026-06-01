import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, Film, Images, ChevronDown, ChevronUp, Loader2 } from 'lucide-react'
import { createJob } from '../api/client'

const DEFAULT_PARAMS = {
  mode: 'streaming',
  keyframe_interval: '',
  window_size: 64,
  overlap_keyframes: '',
  camera_num_iterations: 4,
  mask_sky: false,
  conf_threshold: 50,
  fps: 10,
  first_k: '',
  offload_to_cpu: true,
  num_scale_frames: 8,
}

export default function UploadPanel({ onJobCreated }) {
  const [files, setFiles] = useState([])
  const [params, setParams] = useState(DEFAULT_PARAMS)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState(null)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const onDrop = useCallback((accepted) => {
    setFiles(accepted)
    setError(null)
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.jpg', '.jpeg', '.png', '.webp'],
      'video/*': ['.mp4', '.avi', '.mov', '.mkv', '.webm'],
    },
    multiple: true,
  })

  const isVideo =
    files.length === 1 &&
    files[0].type.startsWith('video/')

  const set = (key, value) =>
    setParams((p) => ({ ...p, [key]: value }))

  async function handleSubmit(e) {
    e.preventDefault()
    if (!files.length) return setError('Adicione imagens ou um vídeo.')

    setUploading(true)
    setUploadProgress(0)
    setError(null)

    const cleanParams = {}
    for (const [k, v] of Object.entries(params)) {
      if (v === '' || v === null || v === undefined) continue
      cleanParams[k] = v
    }

    try {
      const job = await createJob(files, cleanParams, setUploadProgress)
      onJobCreated?.(job)
      setFiles([])
      setParams(DEFAULT_PARAMS)
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message ?? 'Erro ao criar job.')
    } finally {
      setUploading(false)
      setUploadProgress(0)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors
          ${isDragActive
            ? 'border-brand-500 bg-brand-500/5'
            : 'border-slate-700 hover:border-slate-600 bg-slate-900/50'}
        `}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center gap-2">
          {files.length === 0 ? (
            <>
              <Upload size={28} className="text-slate-500" />
              <p className="text-sm text-slate-400">
                {isDragActive
                  ? 'Solte aqui…'
                  : 'Arraste imagens / vídeo ou clique para selecionar'}
              </p>
              <p className="text-xs text-slate-600">JPG, PNG, MP4, AVI, MOV, MKV</p>
            </>
          ) : (
            <div className="flex items-center gap-2 text-sm text-slate-300">
              {isVideo ? <Film size={18} /> : <Images size={18} />}
              <span>
                {isVideo
                  ? files[0].name
                  : `${files.length} imagem${files.length > 1 ? 'ns' : ''} selecionada${files.length > 1 ? 's' : ''}`}
              </span>
              <button
                type="button"
                className="text-slate-500 hover:text-slate-300 ml-1 text-xs underline"
                onClick={(ev) => { ev.stopPropagation(); setFiles([]) }}
              >
                limpar
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Basic params */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Modo</label>
          <select
            className="input"
            value={params.mode}
            onChange={(e) => set('mode', e.target.value)}
          >
            <option value="streaming">Streaming</option>
            <option value="windowed">Windowed (sequências longas)</option>
          </select>
        </div>
        <div>
          <label className="label">FPS (extração de vídeo)</label>
          <input
            type="number"
            className="input"
            min={1}
            max={60}
            value={params.fps}
            onChange={(e) => set('fps', Number(e.target.value))}
          />
        </div>
      </div>

      <div className="flex items-center gap-2">
        <input
          id="mask_sky"
          type="checkbox"
          className="rounded border-slate-600 bg-slate-800 text-brand-500 focus:ring-brand-500"
          checked={params.mask_sky}
          onChange={(e) => set('mask_sky', e.target.checked)}
        />
        <label htmlFor="mask_sky" className="text-sm text-slate-300">
          Mascarar céu (cenas externas)
        </label>
      </div>

      {/* Advanced toggle */}
      <button
        type="button"
        className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors"
        onClick={() => setShowAdvanced((v) => !v)}
      >
        {showAdvanced ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        Parâmetros avançados
      </button>

      {showAdvanced && (
        <div className="grid grid-cols-2 gap-3 p-3 bg-slate-900/50 rounded-lg border border-slate-800">
          <div>
            <label className="label">Intervalo de keyframe</label>
            <input
              type="number"
              className="input"
              min={1}
              placeholder="auto"
              value={params.keyframe_interval}
              onChange={(e) => set('keyframe_interval', e.target.value)}
            />
          </div>
          <div>
            <label className="label">Tamanho da janela (windowed)</label>
            <input
              type="number"
              className="input"
              min={8}
              value={params.window_size}
              onChange={(e) => set('window_size', Number(e.target.value))}
            />
          </div>
          <div>
            <label className="label">Iter. câmera (1–8)</label>
            <input
              type="number"
              className="input"
              min={1}
              max={8}
              value={params.camera_num_iterations}
              onChange={(e) => set('camera_num_iterations', Number(e.target.value))}
            />
          </div>
          <div>
            <label className="label">Limiar confiança (%)</label>
            <input
              type="number"
              className="input"
              min={0}
              max={100}
              step={5}
              value={params.conf_threshold}
              onChange={(e) => set('conf_threshold', Number(e.target.value))}
            />
          </div>
          <div>
            <label className="label">Escala de frames iniciais</label>
            <input
              type="number"
              className="input"
              min={1}
              value={params.num_scale_frames}
              onChange={(e) => set('num_scale_frames', Number(e.target.value))}
            />
          </div>
          <div>
            <label className="label">Limitar a N frames</label>
            <input
              type="number"
              className="input"
              min={1}
              placeholder="todos"
              value={params.first_k}
              onChange={(e) => set('first_k', e.target.value)}
            />
          </div>
          <div className="col-span-2 flex items-center gap-2">
            <input
              id="offload"
              type="checkbox"
              className="rounded border-slate-600 bg-slate-800 text-brand-500 focus:ring-brand-500"
              checked={params.offload_to_cpu}
              onChange={(e) => set('offload_to_cpu', e.target.checked)}
            />
            <label htmlFor="offload" className="text-sm text-slate-300">
              Offload para CPU (economiza VRAM)
            </label>
          </div>
        </div>
      )}

      {/* Upload progress */}
      {uploading && uploadProgress > 0 && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-slate-400">
            <span>Enviando arquivos…</span>
            <span>{uploadProgress}%</span>
          </div>
          <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-500 rounded-full transition-all"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

      {error && (
        <p className="text-xs text-red-400 bg-red-500/10 rounded-lg px-3 py-2">{error}</p>
      )}

      <button
        type="submit"
        disabled={uploading || !files.length}
        className="btn-primary w-full justify-center"
      >
        {uploading ? (
          <>
            <Loader2 size={16} className="animate-spin" />
            Enviando…
          </>
        ) : (
          <>
            <Upload size={16} />
            Reconstruir em 3D
          </>
        )}
      </button>
    </form>
  )
}
