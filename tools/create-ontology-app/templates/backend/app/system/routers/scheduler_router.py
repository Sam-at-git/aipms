"""
定时任务管理 API
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.hotel.models.ontology import Employee
from app.security.auth import require_sysadmin
from app.system.services.scheduler_service import SchedulerService

router = APIRouter(prefix="/system/schedulers", tags=["定时任务"])


# ── Pydantic Schemas ──────────────────────────────────

class JobCreate(BaseModel):
    name: str = Field(..., max_length=100)
    code: str = Field(..., max_length=100)
    invoke_target: str = Field(..., max_length=200)
    cron_expression: str = Field(..., max_length=100)
    group: str = Field(default="default", max_length=50)
    misfire_policy: str = Field(default="ignore", max_length=20)
    is_concurrent: bool = False
    is_active: bool = True
    description: Optional[str] = None


class JobUpdate(BaseModel):
    name: Optional[str] = None
    invoke_target: Optional[str] = None
    cron_expression: Optional[str] = None
    group: Optional[str] = None
    misfire_policy: Optional[str] = None
    is_concurrent: Optional[bool] = None
    description: Optional[str] = None


class JobResponse(BaseModel):
    id: int
    name: str
    code: str
    group: str
    invoke_target: str
    cron_expression: str
    misfire_policy: str
    is_concurrent: bool
    is_active: bool
    description: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class JobLogResponse(BaseModel):
    id: int
    job_id: int
    status: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_ms: Optional[int]
    result: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────

@router.get("", response_model=List[JobResponse])
def list_jobs(
    group: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin),
):
    """获取定时任务列表"""
    service = SchedulerService(db)
    return service.list_jobs(group=group, is_active=is_active)


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    body: JobCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin),
):
    """创建定时任务"""
    service = SchedulerService(db)
    existing = service.get_job_by_code(body.code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"任务编码 '{body.code}' 已存在",
        )
    return service.create_job(**body.model_dump())


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin),
):
    """获取任务详情"""
    service = SchedulerService(db)
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: int,
    body: JobUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin),
):
    """更新定时任务"""
    service = SchedulerService(db)
    job = service.update_job(job_id, **body.model_dump(exclude_unset=True))
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin),
):
    """删除定时任务"""
    service = SchedulerService(db)
    if not service.delete_job(job_id):
        raise HTTPException(status_code=404, detail="任务不存在")


@router.post("/{job_id}/start", response_model=JobResponse)
def start_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin),
):
    """启动任务"""
    service = SchedulerService(db)
    job = service.start_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


@router.post("/{job_id}/stop", response_model=JobResponse)
def stop_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin),
):
    """停止任务"""
    service = SchedulerService(db)
    job = service.stop_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


@router.post("/{job_id}/trigger")
def trigger_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin),
):
    """立即执行一次任务"""
    service = SchedulerService(db)
    try:
        result = service.trigger_job(job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


@router.get("/{job_id}/logs", response_model=List[JobLogResponse])
def get_job_logs(
    job_id: int,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_sysadmin),
):
    """获取任务执行日志"""
    service = SchedulerService(db)
    return service.get_job_logs(job_id=job_id, status=status_filter, limit=limit)
