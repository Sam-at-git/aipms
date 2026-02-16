"""
core/engine/event_bus.py

Framework-level event bus - in-memory publish/subscribe pattern.
Implements a lightweight event-driven architecture with synchronous
handlers and error tracking.
"""
from typing import Callable, Dict, List, Any, Optional, Protocol, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
import logging
import threading
import uuid

logger = logging.getLogger(__name__)

# Type aliases
EventId = str
CorrelationId = str


def _generate_event_id() -> EventId:
    """Generate a unique event ID."""
    return f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"


class EventHandler(Protocol):
    """Event handler protocol."""

    def __call__(self, event: "Event") -> None:
        """Handle an event."""
        ...


@dataclass
class Event:
    """
    Event base class.

    Attributes:
        event_type: Event type (e.g., "room.status_changed")
        timestamp: Event timestamp
        data: Event data payload
        source: Trigger source (service name)
        event_id: Unique event ID
        correlation_id: Correlation ID (for event chain tracing)
    """

    event_type: str
    timestamp: datetime
    data: Dict[str, Any]
    source: str = ""
    event_id: EventId = field(default_factory=_generate_event_id)
    correlation_id: Optional[CorrelationId] = None

    def with_correlation(self, parent_id: EventId) -> "Event":
        """
        Set the correlation ID from a parent event.

        Args:
            parent_id: Parent event ID.

        Returns:
            This event with correlation_id set.
        """
        self.correlation_id = parent_id
        return self


@dataclass
class PublishResult:
    """
    Event publish result.

    Attributes:
        event_type: Event type
        subscriber_count: Number of subscribers
        success_count: Number of successfully handled events
        failure_count: Number of failed handlers
        errors: List of (handler, exception) tuples
    """

    event_type: str
    subscriber_count: int
    success_count: int
    failure_count: int
    errors: List[Tuple[Callable, Exception]] = field(default_factory=list)


@dataclass
class EventBusStatistics:
    """
    Event bus statistics.

    Attributes:
        total_published: Total events published
        total_processed: Total successfully processed
        total_failed: Total failed
        subscriber_count: Subscriber count per event type
    """

    total_published: int = 0
    total_processed: int = 0
    total_failed: int = 0
    subscriber_count: Dict[str, int] = field(default_factory=dict)


class EventBus:
    """
    Framework-level event bus - thread-safe singleton.

    Features:
    - In-memory publish/subscribe pattern
    - Thread-safe subscription management
    - Configurable event history
    - Handler exception isolation
    - Statistics collection

    Example:
        >>> bus = EventBus()
        >>> def handler(event):
        ...     print(f"Received: {event.event_type}")
        >>> bus.subscribe("test.event", handler)
        >>> bus.publish(Event(event_type="test.event", timestamp=datetime.now(), data={}))

    Thread Safety:
        All public methods are thread-safe.
    """

    _instance: Optional["EventBus"] = None
    _lock = threading.Lock()

    def __new__(cls, history_size: int = 100) -> "EventBus":
        """Singleton - ensures a single global instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, history_size: int = 100):
        """
        Initialize the event bus.

        Args:
            history_size: Maximum number of events to keep in history.
        """
        if self._initialized:
            return

        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._event_history: deque[Event] = deque(maxlen=history_size)
        self._subscriber_lock = threading.RLock()

        # Statistics
        self._stats = EventBusStatistics()
        self._stats_lock = threading.Lock()

        self._history_size = history_size
        self._initialized = True
        logger.info("EventBus initialized")

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        Subscribe to an event type.

        Args:
            event_type: Event type (e.g., "room.status_changed")
            handler: Handler function that accepts an Event parameter.

        Example:
            >>> def my_handler(event: Event) -> None:
            ...     print(event.data)
            >>> bus.subscribe("my.event", my_handler)
        """
        with self._subscriber_lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)
                logger.info(f"Handler {handler.__name__} subscribed to {event_type}")

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        Unsubscribe from an event type.

        Args:
            event_type: Event type.
            handler: Handler to remove.
        """
        with self._subscriber_lock:
            if event_type in self._subscribers and handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)
                logger.info(f"Handler {handler.__name__} unsubscribed from {event_type}")

    def publish(self, event: Event) -> PublishResult:
        """
        Publish an event (synchronously executes all handlers).

        Handler exceptions do not affect other handlers.

        Args:
            event: The event to publish.

        Returns:
            PublishResult with processing statistics.
        """
        # Record event
        self._event_history.append(event)

        # Copy handlers under lock to avoid holding lock during execution
        with self._subscriber_lock:
            handlers = self._subscribers.get(event.event_type, []).copy()

        # Update statistics
        with self._stats_lock:
            self._stats.total_published += 1

        result = PublishResult(
            event_type=event.event_type,
            subscriber_count=len(handlers),
            success_count=0,
            failure_count=0,
            errors=[],
        )

        if handlers:
            logger.info(f"Publishing {event.event_type} to {len(handlers)} handlers")

        for handler in handlers:
            try:
                handler(event)
                result.success_count += 1
                with self._stats_lock:
                    self._stats.total_processed += 1
            except Exception as e:
                result.failure_count += 1
                result.errors.append((handler, e))
                with self._stats_lock:
                    self._stats.total_failed += 1
                logger.error(
                    f"Event handler {handler.__name__} error for {event.event_type}: {e}",
                    exc_info=True,
                )

        return result

    def publish_many(self, events: List[Event]) -> List[PublishResult]:
        """
        Publish multiple events.

        Args:
            events: List of events.

        Returns:
            List of PublishResult for each event.

        Example:
            >>> events = [
            ...     Event(event_type="e1", timestamp=datetime.now(), data={}),
            ...     Event(event_type="e2", timestamp=datetime.now(), data={}),
            ... ]
            >>> results = bus.publish_many(events)
            >>> for r in results:
            ...     print(f"{r.event_type}: {r.success_count} successes")
        """
        return [self.publish(event) for event in events]

    def get_history(
        self, event_type: Optional[str] = None, limit: int = 50
    ) -> List[Event]:
        """
        Get event history (for debugging).

        Args:
            event_type: Optional filter for a specific event type.
            limit: Maximum number of results.

        Returns:
            List of events, newest first.
        """
        history = list(self._event_history)
        if event_type:
            history = [e for e in history if e.event_type == event_type]
        return list(reversed(history))[:limit]

    def get_subscribers(
        self, event_type: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """
        Get subscriber information (for debugging).

        Args:
            event_type: Optional filter for a specific type.

        Returns:
            Mapping of event types to handler name lists.
        """
        with self._subscriber_lock:
            if event_type:
                handlers = self._subscribers.get(event_type, [])
                return {event_type: [h.__name__ for h in handlers]}
            return {
                et: [h.__name__ for h in handlers]
                for et, handlers in self._subscribers.items()
            }

    def get_statistics(self) -> EventBusStatistics:
        """
        Get event bus statistics.

        Returns:
            A copy of the EventBusStatistics.
        """
        with self._stats_lock:
            stats = EventBusStatistics(
                total_published=self._stats.total_published,
                total_processed=self._stats.total_processed,
                total_failed=self._stats.total_failed,
            )

        with self._subscriber_lock:
            stats.subscriber_count = {
                et: len(handlers) for et, handlers in self._subscribers.items()
            }

        return stats

    def clear_subscribers(self) -> None:
        """
        Clear all subscriptions (for testing).

        Warning:
            This clears all subscriptions. Only use in test environments.
        """
        with self._subscriber_lock:
            self._subscribers.clear()
        logger.info("All subscribers cleared")

    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history.clear()

    def set_history_size(self, size: int) -> None:
        """
        Set the history size (clears existing history).

        Args:
            size: New history size.
        """
        self._history_size = size
        self._event_history = deque(maxlen=size)

    def reset_statistics(self) -> None:
        """
        Reset statistics (for testing).

        Warning:
            This resets all statistics. Only use in test environments.
        """
        with self._stats_lock:
            self._stats = EventBusStatistics()

    def clear(self) -> None:
        """
        Fully clear the event bus (for testing).

        Warning:
            This clears all data. Only use in test environments.
        """
        self.clear_subscribers()
        self.clear_history()
        self.reset_statistics()


# Global event bus instance
event_bus = EventBus()


__all__ = [
    "EventId",
    "CorrelationId",
    "EventHandler",
    "Event",
    "PublishResult",
    "EventBusStatistics",
    "EventBus",
    "event_bus",
]
