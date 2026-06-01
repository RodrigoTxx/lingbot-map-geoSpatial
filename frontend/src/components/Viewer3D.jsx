import { Suspense, useRef, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, useGLTF, Grid, GizmoHelper, GizmoViewport, Stats } from '@react-three/drei'
import { Download, Maximize2, Info } from 'lucide-react'
import { resultUrl } from '../api/client'

// ── 3D Scene ──────────────────────────────────────────────────
function PointCloudScene({ url }) {
  const { scene } = useGLTF(url, true)
  return <primitive object={scene} />
}

function LoadingFallback() {
  return (
    <mesh>
      <boxGeometry args={[0.3, 0.3, 0.3]} />
      <meshStandardMaterial color="#3b82f6" wireframe />
    </mesh>
  )
}

// ── Viewer component ──────────────────────────────────────────
export default function Viewer3D({ jobId }) {
  const glbUrl = resultUrl(jobId)
  const [showStats, setShowStats] = useState(false)
  const containerRef = useRef(null)

  function handleDownload() {
    const a = document.createElement('a')
    a.href = glbUrl
    a.download = `lingbot_map_${jobId.slice(0, 8)}.glb`
    a.click()
  }

  function handleFullscreen() {
    containerRef.current?.requestFullscreen?.()
  }

  return (
    <div ref={containerRef} className="relative w-full h-full bg-slate-950 rounded-xl overflow-hidden">
      {/* Toolbar */}
      <div className="absolute top-3 right-3 z-10 flex items-center gap-1">
        <button
          className="btn-ghost bg-slate-900/80 backdrop-blur-sm border border-slate-800"
          onClick={() => setShowStats((v) => !v)}
          title="Mostrar estatísticas"
        >
          <Info size={14} />
        </button>
        <button
          className="btn-ghost bg-slate-900/80 backdrop-blur-sm border border-slate-800"
          onClick={handleDownload}
          title="Baixar GLB"
        >
          <Download size={14} />
          <span className="hidden sm:block">Baixar GLB</span>
        </button>
        <button
          className="btn-ghost bg-slate-900/80 backdrop-blur-sm border border-slate-800"
          onClick={handleFullscreen}
          title="Tela cheia"
        >
          <Maximize2 size={14} />
        </button>
      </div>

      {/* Hint */}
      <div className="absolute bottom-3 left-3 z-10 text-xs text-slate-600 pointer-events-none">
        Arraste para orbitar · Scroll para zoom · Shift+arraste para mover
      </div>

      <Canvas
        camera={{ position: [0, 8, 20], fov: 55, near: 0.01, far: 10000 }}
        gl={{ antialias: true, alpha: false }}
        dpr={[1, 2]}
      >
        {/* Scene background */}
        <color attach="background" args={['#020617']} />

        {/* Lighting */}
        <ambientLight intensity={0.8} />
        <directionalLight position={[20, 30, 10]} intensity={1.2} castShadow />
        <directionalLight position={[-10, -10, -5]} intensity={0.3} />

        {/* Point cloud / cameras from GLB */}
        <Suspense fallback={<LoadingFallback />}>
          <PointCloudScene url={glbUrl} />
        </Suspense>

        {/* Reference grid */}
        <Grid
          args={[200, 200]}
          position={[0, -0.5, 0]}
          cellColor="#1e293b"
          sectionColor="#334155"
          fadeDistance={100}
          infiniteGrid
        />

        {/* Controls */}
        <OrbitControls
          makeDefault
          enableDamping
          dampingFactor={0.08}
          minDistance={0.1}
          maxDistance={5000}
        />

        {/* Gizmo (orientation cube) */}
        <GizmoHelper alignment="bottom-right" margin={[60, 60]}>
          <GizmoViewport
            axisColors={['#f87171', '#4ade80', '#60a5fa']}
            labelColor="white"
          />
        </GizmoHelper>

        {showStats && <Stats />}
      </Canvas>
    </div>
  )
}
