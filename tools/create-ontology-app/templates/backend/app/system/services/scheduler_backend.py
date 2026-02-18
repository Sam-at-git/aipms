"""
APScheduler 调度后端 — 实现 core 层 ISchedulerBackend 接口
"""
import logging
from typing import Callable, Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from core.scheduler import ISchedulerBackend

logger = logging.getLogger(__name__)


class APSchedulerBackend(ISchedulerBackend):
    """基于 APScheduler 的调度后端"""

    def __init__(self, scheduler: Optional[BackgroundScheduler] = None):
        self._scheduler = scheduler or BackgroundScheduler()

    @property
    def scheduler(self) -> BackgroundScheduler:
        return self._scheduler

    def start(self) -> None:
        """启动调度器"""
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("APScheduler started")

    def shutdown(self) -> None:
        """关闭调度器"""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("APScheduler shut down")

    def add_job(
        self,
        job_id: str,
        func: Callable,
        trigger: str,
        **trigger_args,
    ) -> None:
        """添加定时任务"""
        if trigger == "cron" and "cron_expression" in trigger_args:
            expr = trigger_args.pop("cron_expression")
            cron_trigger = CronTrigger.from_crontab(expr)
            self._scheduler.add_job(
                func,
                trigger=cron_trigger,
                id=job_id,
                replace_existing=True,
                **trigger_args,
            )
        else:
            self._scheduler.add_job(
                func,
                trigger=trigger,
                id=job_id,
                replace_existing=True,
                **trigger_args,
            )
        logger.info(f"Job added: {job_id}")

    def remove_job(self, job_id: str) -> None:
        """移除任务"""
        try:
            self._scheduler.remove_job(job_id)
            logger.info(f"Job removed: {job_id}")
        except Exception:
            logger.warning(f"Job not found for removal: {job_id}")

    def pause_job(self, job_id: str) -> None:
        """暂停任务"""
        self._scheduler.pause_job(job_id)
        logger.info(f"Job paused: {job_id}")

    def resume_job(self, job_id: str) -> None:
        """恢复任务"""
        self._scheduler.resume_job(job_id)
        logger.info(f"Job resumed: {job_id}")

    def get_jobs(self) -> List[Dict]:
        """获取所有任务"""
        jobs = self._scheduler.get_jobs()
        return [self._job_to_dict(j) for j in jobs]

    def get_job(self, job_id: str) -> Optional[Dict]:
        """获取单个任务"""
        job = self._scheduler.get_job(job_id)
        if job is None:
            return None
        return self._job_to_dict(job)

    def trigger_job(self, job_id: str) -> None:
        """立即触发一次任务"""
        job = self._scheduler.get_job(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")
        job.func()

    @staticmethod
    def _job_to_dict(job) -> Dict:
        return {
            "id": job.id,
            "name": job.name or job.id,
            "trigger": str(job.trigger),
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "status": "paused" if job.next_run_time is None else "active",
        }
