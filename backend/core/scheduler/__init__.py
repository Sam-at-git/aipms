"""
调度器接口 — 域无关的定时任务抽象

app 层通过实现 ISchedulerBackend 来对接具体调度框架（APScheduler 等）。
"""
from core.scheduler.base import ISchedulerBackend, SchedulerRegistry

__all__ = ["ISchedulerBackend", "SchedulerRegistry"]
