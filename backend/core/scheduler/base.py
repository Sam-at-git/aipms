"""
Scheduler backend interface - domain-agnostic scheduled task abstraction.

The app layer implements ISchedulerBackend to connect to a specific
scheduling framework (APScheduler, etc.).
"""
from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Optional
import threading


class ISchedulerBackend(ABC):
    """Scheduler backend interface."""

    @abstractmethod
    def add_job(
        self,
        job_id: str,
        func: Callable,
        trigger: str,
        **trigger_args,
    ) -> None:
        """Add a scheduled job.

        Args:
            job_id: Unique job identifier
            func: Function to execute
            trigger: Trigger type ('cron', 'interval', 'date')
            **trigger_args: Trigger parameters (e.g., cron expression fields)
        """

    @abstractmethod
    def remove_job(self, job_id: str) -> None:
        """Remove a job."""

    @abstractmethod
    def pause_job(self, job_id: str) -> None:
        """Pause a job."""

    @abstractmethod
    def resume_job(self, job_id: str) -> None:
        """Resume a job."""

    @abstractmethod
    def get_jobs(self) -> List[Dict]:
        """Get all jobs.

        Returns:
            List of jobs, each containing at least id, name, trigger, next_run_time, status.
        """

    @abstractmethod
    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get a single job's information."""

    @abstractmethod
    def trigger_job(self, job_id: str) -> None:
        """Trigger an immediate execution of a job."""


class SchedulerRegistry:
    """Scheduler registry - singleton.

    The app layer registers the implementation at startup:
        from core.scheduler import SchedulerRegistry
        registry = SchedulerRegistry()
        registry.set_backend(APSchedulerBackend(scheduler))
    """

    _instance: Optional["SchedulerRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "SchedulerRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._backend: Optional[ISchedulerBackend] = None
        return cls._instance

    def set_backend(self, backend: ISchedulerBackend) -> None:
        """Register the scheduler backend."""
        self._backend = backend

    def get_backend(self) -> Optional[ISchedulerBackend]:
        """Get the scheduler backend."""
        return self._backend

    def clear(self) -> None:
        """Clear the backend (for testing)."""
        self._backend = None


__all__ = [
    "ISchedulerBackend",
    "SchedulerRegistry",
]
