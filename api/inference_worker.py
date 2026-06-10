"""Background inference worker with a single-GPU job queue.

Jobs are processed sequentially — the GPU can only run one reconstruction
at a time.  The model is loaded once at worker startup.
"""

from __future__ import annotations

import contextlib
import logging
import os
import queue
import shutil
import sys
import threading
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared in-memory job store (protected by _JOBS_LOCK)
# ---------------------------------------------------------------------------
JOBS: Dict[str, Dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _update_job(job_id: str, **kwargs: Any) -> None:
    with _JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(kwargs)


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class InferenceWorker:
    """Single-GPU inference worker.  One job processed at a time."""

    def __init__(self, model_path: str, use_sdpa: bool = False) -> None:
        self.model_path = model_path
        self.use_sdpa = use_sdpa

        self._queue: queue.Queue[Optional[str]] = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._start_lock = threading.Lock()

        # Set after _load_model()
        self._model = None
        self._device = None
        self._dtype = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        with self._start_lock:
            if self._thread and self._thread.is_alive():
                return

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run, daemon=True, name="inference-worker"
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._queue.put(None)  # unblock the worker loop
        if self._thread:
            self._thread.join(timeout=10)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(self, job_id: str, upload_dir: str, params: dict) -> None:
        with _JOBS_LOCK:
            JOBS[job_id] = {
                "id": job_id,
                "status": "queued",
                "progress": 0,
                "message": "Aguardando na fila...",
                "created_at": _now_iso(),
                "started_at": None,
                "finished_at": None,
                "upload_dir": upload_dir,
                "params": params,
                "result_path": None,
                "error": None,
            }

        # Guarantee there is a live consumer before queueing the job.
        if not self.is_alive:
            logger.warning("Inference worker thread not alive; restarting.")
            self.start()

        self._queue.put(job_id)
        logger.info("Job %s enqueued", job_id)

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def model_loaded(self) -> bool:
        return self._model is not None

    # ------------------------------------------------------------------
    # Internal worker loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        self._load_model()
        while not self._stop_event.is_set():
            try:
                job_id = self._queue.get(timeout=1)
            except queue.Empty:
                continue
            if job_id is None:  # sentinel
                break
            self._process_job(job_id)

    def _load_model(self) -> None:
        if not self.model_path:
            logger.warning(
                "MODEL_PATH não configurado — inferência falhará até o modelo ser montado."
            )
            return

        if not os.path.exists(self.model_path):
            logger.error("Checkpoint não encontrado em %s", self.model_path)
            return

        # Defer heavy imports
        import torch  # noqa: PLC0415

        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if torch.cuda.is_available():
            cap = torch.cuda.get_device_capability()[0]
            self._dtype = torch.bfloat16 if cap >= 8 else torch.float16
        else:
            self._dtype = torch.float32

        logger.info(
            "Carregando modelo de %s em %s (dtype=%s)…",
            self.model_path, self._device, self._dtype,
        )
        try:
            from lingbot_map.models.gct_stream import GCTStream  # noqa: PLC0415

            model = GCTStream(
                img_size=518,
                patch_size=14,
                enable_3d_rope=True,
                max_frame_num=1024,
                kv_cache_sliding_window=64,
                kv_cache_scale_frames=8,
                kv_cache_cross_frame_special=True,
                kv_cache_include_scale_frames=True,
                use_sdpa=self.use_sdpa,
                camera_num_iterations=4,
            )
            ckpt = torch.load(
                self.model_path, map_location=self._device, weights_only=False
            )
            state_dict = ckpt.get("model", ckpt)
            missing, unexpected = model.load_state_dict(state_dict, strict=False)
            if missing:
                logger.info("  Chaves ausentes: %d", len(missing))
            if unexpected:
                logger.info("  Chaves inesperadas: %d", len(unexpected))

            model = model.to(self._device).eval()

            # Cast trunk to inference dtype (saves ~2-3 GB, no quality impact)
            if self._dtype != torch.float32 and hasattr(model, "aggregator"):
                model.aggregator = model.aggregator.to(dtype=self._dtype)

            self._model = model
            logger.info("Modelo carregado com sucesso.")
        except Exception:
            logger.exception("Falha ao carregar modelo")

    # ------------------------------------------------------------------
    # Job processing
    # ------------------------------------------------------------------

    def _process_job(self, job_id: str) -> None:
        with _JOBS_LOCK:
            job = JOBS.get(job_id)
        if job is None:
            return

        upload_dir: str = job["upload_dir"]
        params: dict = job["params"]
        result_dir = os.path.join(upload_dir, "results")
        os.makedirs(result_dir, exist_ok=True)

        try:
            self._run_inference(job_id, upload_dir, params, result_dir)
        except Exception:
            err = traceback.format_exc()
            logger.error("Job %s falhou:\n%s", job_id, err)
            _update_job(
                job_id,
                status="failed",
                progress=0,
                message=f"Erro: {err.splitlines()[-1]}",
                finished_at=_now_iso(),
                error=err,
            )
        finally:
            # Remove raw upload files, keep results
            for subdir in ("images", "frames"):
                p = os.path.join(upload_dir, subdir)
                if os.path.exists(p):
                    shutil.rmtree(p, ignore_errors=True)

    def _run_inference(
        self,
        job_id: str,
        upload_dir: str,
        params: dict,
        result_dir: str,
    ) -> None:
        import torch  # noqa: PLC0415

        # Defer project imports (heavy, GPU)
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from demo import load_images, postprocess, prepare_for_visualization  # noqa: PLC0415
        from lingbot_map.vis.glb_export import predictions_to_glb  # noqa: PLC0415

        _update_job(
            job_id,
            status="running",
            started_at=_now_iso(),
            progress=5,
            message="Carregando imagens…",
        )

        # ── Locate source files ───────────────────────────────────────
        images_dir = os.path.join(upload_dir, "images")
        video_path: Optional[str] = None
        for fname in os.listdir(upload_dir):
            if fname.lower().split(".")[-1] in ("mp4", "avi", "mov", "mkv", "webm"):
                video_path = os.path.join(upload_dir, fname)
                break

        img_folder = images_dir if os.path.isdir(images_dir) else None

        images, _paths, resolved_folder = load_images(
            image_folder=img_folder,
            video_path=video_path,
            fps=params.get("fps", 10),
            first_k=params.get("first_k"),
            stride=params.get("stride", 1),
            image_size=518,
            patch_size=14,
        )

        num_frames = int(images.shape[0])
        _update_job(
            job_id,
            progress=20,
            message=f"Carregados {num_frames} quadros. Iniciando inferência…",
        )

        # ── Validate model ────────────────────────────────────────────
        if self._model is None:
            raise RuntimeError(
                "Modelo não carregado. Verifique a variável MODEL_PATH."
            )

        # ── Auto keyframe interval ────────────────────────────────────
        kf_int = params.get("keyframe_interval")
        mode: str = params.get("mode", "streaming")
        if kf_int is None:
            if mode == "streaming" and num_frames > 320:
                kf_int = (num_frames + 319) // 320
            else:
                kf_int = 1

        num_scale = params.get("num_scale_frames", 8)
        offload = params.get("offload_to_cpu", True)
        output_device = torch.device("cpu") if offload else None

        images = images.to(self._device)
        if self._device.type == "cuda":
            torch.cuda.empty_cache()

        # ── Run inference ─────────────────────────────────────────────
        _update_job(job_id, progress=25, message="Executando reconstrução 3D…")

        autocast_ctx: Any
        if self._device.type == "cuda":
            autocast_ctx = torch.amp.autocast("cuda", dtype=self._dtype)
        else:
            autocast_ctx = contextlib.nullcontext()

        with torch.no_grad(), autocast_ctx:
            if mode == "streaming":
                predictions = self._model.inference_streaming(
                    images,
                    num_scale_frames=num_scale,
                    keyframe_interval=kf_int,
                    output_device=output_device,
                )
            else:
                predictions = self._model.inference_windowed(
                    images,
                    window_size=params.get("window_size", 64),
                    overlap_size=params.get("overlap_size", 16),
                    overlap_keyframes=params.get("overlap_keyframes"),
                    num_scale_frames=num_scale,
                    keyframe_interval=kf_int,
                    output_device=output_device,
                )

        _update_job(job_id, progress=80, message="Pós-processando resultados…")

        images_for_post = predictions["images"] if offload else images
        predictions, images_cpu = postprocess(predictions, images_for_post)

        # Free GPU memory as early as possible
        del images
        if self._device.type == "cuda":
            torch.cuda.empty_cache()

        _update_job(job_id, progress=90, message="Exportando nuvem de pontos 3D…")

        vis_preds = prepare_for_visualization(predictions, images_cpu)

        # If the model ran without point_head (enable_point=False, the default),
        # world_points is absent. Compute it from depth + camera params so
        # predictions_to_glb can fall back to "world_points_from_depth".
        if "world_points" not in vis_preds and "depth" in vis_preds:
            from lingbot_map.utils.geometry import unproject_depth_map_to_point_map  # noqa: PLC0415
            depth_np = vis_preds["depth"]          # (S, H, W, 1)
            extrinsic_np = vis_preds["extrinsic"]  # (S, 3, 4)  c2w
            intrinsic_np = vis_preds["intrinsic"]  # (S, 3, 3)
            vis_preds["world_points_from_depth"] = unproject_depth_map_to_point_map(
                depth_np, extrinsic_np, intrinsic_np
            )
            vis_preds["depth_conf"] = vis_preds.get("depth_conf")

        scene = predictions_to_glb(
            vis_preds,
            conf_thres=params.get("conf_threshold", 50.0),
            show_cam=True,
            mask_sky=params.get("mask_sky", False),
            target_dir=result_dir,
        )

        glb_path = os.path.join(result_dir, f"{job_id}.glb")
        scene.export(glb_path)

        _update_job(
            job_id,
            status="completed",
            progress=100,
            message="Reconstrução concluída!",
            finished_at=_now_iso(),
            result_path=glb_path,
        )
        logger.info("Job %s concluído → %s", job_id, glb_path)
