"""
定时任务服务 — CRUD + 调度管理 + 执行日志
"""
import importlib
import logging
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.system.models.scheduler import SysJob, SysJobLog
from app.system.services.scheduler_backend import APSchedulerBackend
from core.scheduler import SchedulerRegistry

logger = logging.getLogger(__name__)


class SchedulerService:
    """定时任务管理服务"""

    def __init__(self, db: Session):
        self.db = db

    # ── CRUD ──────────────────────────────────────────

    def list_jobs(
        self,
        group: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[SysJob]:
        """获取任务列表"""
        query = self.db.query(SysJob)
        if group:
            query = query.filter(SysJob.group == group)
        if is_active is not None:
            query = query.filter(SysJob.is_active == is_active)
        return query.order_by(SysJob.id).all()

    def get_job(self, job_id: int) -> Optional[SysJob]:
        """获取任务详情"""
        return self.db.query(SysJob).filter(SysJob.id == job_id).first()

    def get_job_by_code(self, code: str) -> Optional[SysJob]:
        """通过 code 获取任务"""
        return self.db.query(SysJob).filter(SysJob.code == code).first()

    def create_job(
        self,
        name: str,
        code: str,
        invoke_target: str,
        cron_expression: str,
        group: str = "default",
        misfire_policy: str = "ignore",
        is_concurrent: bool = False,
        is_active: bool = True,
        description: Optional[str] = None,
    ) -> SysJob:
        """创建定时任务"""
        job = SysJob(
            name=name,
            code=code,
            invoke_target=invoke_target,
            cron_expression=cron_expression,
            group=group,
            misfire_policy=misfire_policy,
            is_concurrent=is_concurrent,
            is_active=is_active,
            description=description,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        # If active, register with scheduler backend
        if is_active:
            self._register_job(job)

        return job

    def update_job(self, job_id: int, **kwargs) -> Optional[SysJob]:
        """更新定时任务"""
        job = self.get_job(job_id)
        if not job:
            return None

        for key, value in kwargs.items():
            if hasattr(job, key):
                setattr(job, key, value)
        job.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(job)

        # Re-register with scheduler
        self._unregister_job(job.code)
        if job.is_active:
            self._register_job(job)

        return job

    def delete_job(self, job_id: int) -> bool:
        """删除定时任务"""
        job = self.get_job(job_id)
        if not job:
            return False

        self._unregister_job(job.code)
        self.db.delete(job)
        self.db.commit()
        return True

    # ── 调度操作 ──────────────────────────────────────

    def start_job(self, job_id: int) -> Optional[SysJob]:
        """启动任务"""
        job = self.get_job(job_id)
        if not job:
            return None
        job.is_active = True
        job.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(job)
        self._register_job(job)
        return job

    def stop_job(self, job_id: int) -> Optional[SysJob]:
        """停止任务"""
        job = self.get_job(job_id)
        if not job:
            return None
        job.is_active = False
        job.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(job)
        self._unregister_job(job.code)
        return job

    def trigger_job(self, job_id: int) -> Dict:
        """立即执行一次任务"""
        job = self.get_job(job_id)
        if not job:
            raise ValueError("任务不存在")

        func = self._resolve_target(job.invoke_target)
        start_time = datetime.utcnow()
        status = "success"
        result_text = None
        try:
            result = func()
            result_text = str(result) if result else "OK"
        except Exception as e:
            status = "fail"
            result_text = str(e)
            logger.error(f"Job {job.code} execution failed: {e}")

        end_time = datetime.utcnow()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        log = SysJobLog(
            job_id=job.id,
            status=status,
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            result=result_text,
        )
        self.db.add(log)
        self.db.commit()

        return {
            "success": status == "success",
            "status": status,
            "duration_ms": duration_ms,
            "result": result_text,
        }

    # ── 执行日志 ──────────────────────────────────────

    def get_job_logs(
        self,
        job_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[SysJobLog]:
        """获取执行日志"""
        query = self.db.query(SysJobLog)
        if job_id:
            query = query.filter(SysJobLog.job_id == job_id)
        if status:
            query = query.filter(SysJobLog.status == status)
        return query.order_by(SysJobLog.created_at.desc()).limit(limit).all()

    # ── 启动时加载 ────────────────────────────────────

    def load_active_jobs(self) -> int:
        """启动时加载所有活跃任务到调度器"""
        active_jobs = self.list_jobs(is_active=True)
        count = 0
        for job in active_jobs:
            try:
                self._register_job(job)
                count += 1
            except Exception as e:
                logger.error(f"Failed to load job {job.code}: {e}")
        logger.info(f"Loaded {count}/{len(active_jobs)} active jobs")
        return count

    # ── 内部方法 ──────────────────────────────────────

    def _register_job(self, job: SysJob) -> None:
        """将任务注册到调度后端"""
        backend = SchedulerRegistry().get_backend()
        if backend is None:
            logger.warning("No scheduler backend registered, skipping job registration")
            return

        func = self._resolve_target(job.invoke_target)
        backend.add_job(
            job_id=job.code,
            func=func,
            trigger="cron",
            cron_expression=job.cron_expression,
        )

    def _unregister_job(self, code: str) -> None:
        """从调度后端移除任务"""
        backend = SchedulerRegistry().get_backend()
        if backend is None:
            return
        backend.remove_job(code)

    @staticmethod
    def _resolve_target(invoke_target: str):
        """解析 invoke_target (module.path:function_name) 为可调用对象"""
        if ":" not in invoke_target:
            raise ValueError(f"Invalid invoke_target format: {invoke_target} (expected module.path:func)")

        module_path, func_name = invoke_target.rsplit(":", 1)
        module = importlib.import_module(module_path)
        func = getattr(module, func_name, None)
        if func is None:
            raise ValueError(f"Function '{func_name}' not found in module '{module_path}'")
        return func
