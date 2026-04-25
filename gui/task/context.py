from abc import ABC, abstractmethod
from uuid import uuid4

class Context(ABC):
    """Shared worker-side runtime setup for a group of related tasks.

    A Context instance is identified by a UUID assigned at construction.
    When a worker process receives a task that references a context, it
    calls ``setup()`` on first encounter and caches the live instance
    for the lifetime of the worker.  Subsequent tasks with the same UUID
    on the same worker reuse the cached instance without calling ``setup``
    again.

    Call ``release()`` when the context is no longer needed.  This fans
    out ``teardown()`` to every worker that may hold a cached copy.
    """

    def __init__(self) -> None:
        self.uuid: str = str(uuid4())

    @abstractmethod
    def setup(self) -> None:
        """Initialise any worker-side resources (e.g. open file handles).

        Called at most once per worker process per Context instance.
        """

    def teardown(self) -> None:
        """Release worker-side resources held by this context.

        Called when ``release()`` is invoked on the main process.
        Override as needed; default is a no-op.
        """

    def release(self) -> None:
        """Fan out teardown to all worker processes and mark as released.

        Delegates to ``gui.task.release_context``.  Importing here
        (inside the method) avoids a circular import at module load time.
        """
        import gui.task as _task_module  # noqa: PLC0415

        _task_module.release_context(self)
