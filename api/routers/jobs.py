"""Job CRUD and WebSocket endpoints."""

from __future__ import annotations

import asyncio
import os
import shutil
import uuid
from typing import List, Optional

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse

from ..inference_worker import JOBS, _JOBS_LOCK

router = APIRouter()

UPLOAD_BASE: str = os.environ.get("UPLOAD_BASE", "/tmp/lingbot_uploads")

# Maximum upload size: 4 GB per request
_MAX_UPLOAD_BYTES = 4 * 1024 * 1024 * 1024

_VIDEO_EXTS = frozenset((".mp4", ".avi", ".mov", ".mkv", ".webm"))


# ---------------------------------------------------------------------------
# POST /api/jobs  — create a new reconstruction job
# ---------------------------------------------------------------------------

@router.post("", status_code=202)
async def create_job(
    request: Request,
    files: List[UploadFile] = File(...),
    mode: str = Form("streaming"),
    keyframe_interval: Optional[int] = Form(None),
    window_size: int = Form(64),
    overlap_keyframes: Optional[int] = Form(None),
    camera_num_iterations: int = Form(4),
    mask_sky: bool = Form(False),
    conf_threshold: float = Form(50.0),
    fps: int = Form(10),
    first_k: Optional[int] = Form(None),
    offload_to_cpu: bool = Form(True),
    num_scale_frames: int = Form(8),
):
    job_id = str(uuid.uuid4())
    upload_dir = os.path.join(UPLOAD_BASE, job_id)
    os.makedirs(upload_dir, exist_ok=True)

    try:
        # ── Save uploaded files ──────────────────────────────────────
        is_video = any(
            os.path.splitext(f.filename.lower())[1] in _VIDEO_EXTS for f in files
        )

        if is_video:
            video_file = next(
                f
                for f in files
                if os.path.splitext(f.filename.lower())[1] in _VIDEO_EXTS
            )
            ext = os.path.splitext(video_file.filename.lower())[1]
            dest = os.path.join(upload_dir, f"input{ext}")
            with open(dest, "wb") as out:
                while chunk := await video_file.read(1024 * 1024):
                    out.write(chunk)
        else:
            images_dir = os.path.join(upload_dir, "images")
            os.makedirs(images_dir, exist_ok=True)
            for f in files:
                # Sanitize filename to prevent path traversal
                safe_name = os.path.basename(f.filename)
                dest = os.path.join(images_dir, safe_name)
                with open(dest, "wb") as out:
                    while chunk := await f.read(1024 * 1024):
                        out.write(chunk)

        # ── Enqueue job ───────────────────────────────────────────────
        params = {
            "mode": mode,
            "keyframe_interval": keyframe_interval,
            "window_size": window_size,
            "overlap_keyframes": overlap_keyframes,
            "camera_num_iterations": camera_num_iterations,
            "mask_sky": mask_sky,
            "conf_threshold": conf_threshold,
            "fps": fps,
            "first_k": first_k,
            "offload_to_cpu": offload_to_cpu,
            "num_scale_frames": num_scale_frames,
        }

        worker = request.app.state.worker
        worker.enqueue(job_id, upload_dir, params)

        return {"id": job_id, "status": "queued"}

    except Exception:
        # Clean up on upload error
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise


# ---------------------------------------------------------------------------
# GET /api/jobs  — list all jobs
# ---------------------------------------------------------------------------

@router.get("")
def list_jobs():
    with _JOBS_LOCK:
        return [
            _public_view(j) for j in JOBS.values()
        ]


# ---------------------------------------------------------------------------
# GET /api/jobs/{id}  — get single job
# ---------------------------------------------------------------------------

@router.get("/{job_id}")
def get_job(job_id: str):
    with _JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return _public_view(job)


# ---------------------------------------------------------------------------
# GET /api/jobs/{id}/result  — download GLB
# ---------------------------------------------------------------------------

@router.get("/{job_id}/result")
def get_result(job_id: str):
    with _JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job ainda não concluído (status: {job['status']})",
        )
    glb_path: Optional[str] = job.get("result_path")
    if not glb_path or not os.path.exists(glb_path):
        raise HTTPException(status_code=404, detail="Arquivo de resultado não encontrado")
    return FileResponse(
        glb_path,
        media_type="model/gltf-binary",
        filename=f"lingbot_map_{job_id}.glb",
    )


# ---------------------------------------------------------------------------
# DELETE /api/jobs/{id}  — cancel / delete job
# ---------------------------------------------------------------------------

@router.delete("/{job_id}")
def delete_job(job_id: str):
    with _JOBS_LOCK:
        job = JOBS.pop(job_id, None)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    upload_dir = job.get("upload_dir")
    if upload_dir and os.path.exists(upload_dir):
        shutil.rmtree(upload_dir, ignore_errors=True)
    return {"deleted": True}


# ---------------------------------------------------------------------------
# WebSocket /api/jobs/{id}/ws  — real-time progress stream
# ---------------------------------------------------------------------------

@router.websocket("/{job_id}/ws")
async def job_websocket(websocket: WebSocket, job_id: str):
    await websocket.accept()
    try:
        while True:
            with _JOBS_LOCK:
                job = JOBS.get(job_id)

            if job is None:
                await websocket.send_json({"error": "Job não encontrado"})
                break

            await websocket.send_json({
                "id": job["id"],
                "status": job["status"],
                "progress": job["progress"],
                "message": job["message"],
                "error": job.get("error"),
            })

            if job["status"] in ("completed", "failed"):
                break

            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _public_view(job: dict) -> dict:
    """Return a copy of the job dict without internal paths."""
    return {k: v for k, v in job.items() if k not in ("upload_dir", "result_path")}
