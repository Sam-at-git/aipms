"""
调度器后端接口 — 域无关的定时任务抽象

app 层通过实现 ISchedulerBackend 来对接具体调度框架（APScheduler 等）。
"""
from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Optional


class ISchedulerBackend(ABC):
    """调度后端接口"""

    @abstractmethod
    def add_job(
        self,
        job_id: str,
        func: Callable,
        trigger: str,
        **trigger_args,
    ) -> None:
        """添加定时任务

        Args:
            job_id: 任务唯一标识
            func: 要执行的函数
            trigger: 触发器类型（'cron', 'interval', 'date'）
            **trigger_args: 触发器参数（如 cron 表达式字段）
        """

    @abstractmethod
    def remove_job(self, job_id: str) -> None:
        """移除任务"""

    @abstractmethod
    def pause_job(self, job_id: str) -> None:
        """暂停任务"""

    @abstractmethod
    def resume_job(self, job_id: str) -> None:
        """恢复任务"""

    @abstractmethod
    def get_jobs(self) -> List[Dict]:
        """获取所有任务

        Returns:
            任务列表，每项至少包含 id, name, trigger, next_run_time, status
        """

    @abstractmethod
    def get_job(self, job_id: str) -> Optional[Dict]:
        """获取单个任务信息"""

    @abstractmethod
    def trigger_job(self, job_id: str) -> None:
        """立即触发一次任务执行"""


class SchedulerRegistry:
    """调度器注册表 — 单例模式

    app 层在 lifespan 中注册实现：
        from core.scheduler import SchedulerRegistry
        registry = SchedulerRegistry()
        registry.set_backend(APSchedulerBackend(scheduler))
    """

    _instance: Optional["SchedulerRegistry"] = None

    def __new__(cls) -> "SchedulerRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._backend: Optional[ISchedulerBackend] = None
        return cls._instance

    def set_backend(self, backend: ISchedulerBackend) -> None:
        """注册调度后端"""
        self._backend = backend

    def get_backend(self) -> Optional[ISchedulerBackend]:
        """获取调度后端"""
        return self._backend

    def clear(self) -> None:
        """清除后端（用于测试）"""
        self._backend = None
