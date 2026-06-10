"""Health-check endpoints."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health(request: Request):
    worker = request.app.state.worker
    gpu_info = {}
    try:
        import torch  # noqa: PLC0415

        gpu_info["available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            gpu_info["name"] = torch.cuda.get_device_name(0)
            gpu_info["memory_allocated_gb"] = round(
                torch.cuda.memory_allocated() / 1e9, 2
            )
            gpu_info["memory_reserved_gb"] = round(
                torch.cuda.memory_reserved() / 1e9, 2
            )
    except Exception:
        gpu_info["available"] = False

    return {
        "status": "ok",
        "model_loaded": worker.model_loaded,
        "worker_alive": worker.is_alive,
        "gpu": gpu_info,
    }
