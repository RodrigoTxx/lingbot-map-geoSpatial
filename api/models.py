"""Pydantic models for the LingBot-Map API."""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class JobParams(BaseModel):
    mode: Literal["streaming", "windowed"] = "streaming"
    keyframe_interval: Optional[int] = Field(None, ge=1)
    window_size: int = Field(64, ge=8)
    overlap_keyframes: Optional[int] = Field(None, ge=1)
    camera_num_iterations: int = Field(4, ge=1, le=8)
    mask_sky: bool = False
    conf_threshold: float = Field(50.0, ge=0.0, le=100.0)
    fps: int = Field(10, ge=1, le=60)
    first_k: Optional[int] = Field(None, ge=1)
    offload_to_cpu: bool = True
    num_scale_frames: int = Field(8, ge=1)


class JobSummary(BaseModel):
    id: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: int
    message: str
    created_at: str
    started_at: Optional[str]
    finished_at: Optional[str]
    error: Optional[str]
    params: dict


class CreateJobResponse(BaseModel):
    id: str
    status: str
