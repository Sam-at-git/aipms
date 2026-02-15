"""
系统实体写操作 Action — 定时任务启停
"""
from typing import Dict, Any
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from core.ai.actions import ActionRegistry
from app.models.ontology import Employee
from app.system.services.scheduler_service import SchedulerService


class SchedulerJobParams(BaseModel):
    job_id: int = Field(..., description="定时任务ID")


def register_system_mutation_actions(registry: ActionRegistry) -> None:
    """Register system entity mutation actions."""

    @registry.register(
        name="start_scheduler_job",
        entity="SysJob",
        description="启动一个定时任务，使其按 Cron 表达式自动执行。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"sysadmin"},
        undoable=False,
        side_effects=["starts_scheduler"],
        search_keywords=["启动任务", "开始任务", "激活任务", "start job", "enable job"],
    )
    def handle_start_job(
        params: SchedulerJobParams,
        db: Session,
        user: Employee,
        **context,
    ) -> Dict[str, Any]:
        service = SchedulerService(db)
        job = service.start_job(params.job_id)
        if not job:
            return {"success": False, "message": f"任务 ID={params.job_id} 不存在"}
        return {
            "success": True,
            "message": f"定时任务 [{job.name}] 已启动",
            "data": {"id": job.id, "name": job.name, "is_active": job.is_active},
        }

    @registry.register(
        name="stop_scheduler_job",
        entity="SysJob",
        description="停止一个定时任务，暂停其自动执行。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"sysadmin"},
        undoable=False,
        side_effects=["stops_scheduler"],
        search_keywords=["停止任务", "暂停任务", "关闭任务", "stop job", "disable job"],
    )
    def handle_stop_job(
        params: SchedulerJobParams,
        db: Session,
        user: Employee,
        **context,
    ) -> Dict[str, Any]:
        service = SchedulerService(db)
        job = service.stop_job(params.job_id)
        if not job:
            return {"success": False, "message": f"任务 ID={params.job_id} 不存在"}
        return {
            "success": True,
            "message": f"定时任务 [{job.name}] 已停止",
            "data": {"id": job.id, "name": job.name, "is_active": job.is_active},
        }

    @registry.register(
        name="trigger_scheduler_job",
        entity="SysJob",
        description="立即触发一次定时任务执行（不影响调度计划）。",
        category="mutation",
        requires_confirmation=True,
        allowed_roles={"sysadmin"},
        undoable=False,
        side_effects=["executes_job"],
        search_keywords=["执行任务", "立即执行", "触发任务", "trigger job", "run job"],
    )
    def handle_trigger_job(
        params: SchedulerJobParams,
        db: Session,
        user: Employee,
        **context,
    ) -> Dict[str, Any]:
        service = SchedulerService(db)
        try:
            result = service.trigger_job(params.job_id)
        except ValueError as e:
            return {"success": False, "message": str(e)}
        return {
            "success": result["success"],
            "message": f"任务执行{'成功' if result['success'] else '失败'} (耗时 {result['duration_ms']}ms)",
            "data": result,
        }
