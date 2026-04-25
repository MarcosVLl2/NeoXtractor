from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, Generic, TypeVar

if TYPE_CHECKING:
    from gui.task.context import Context

T = TypeVar('T')

class Task(ABC, Generic[T]):
    """Abstract base for all submittable units of work.

    Subclasses declare which :class:`~gui.task.context.Context` type they
    need via the ``context_type`` class variable, and store a concrete
    context instance in ``_context`` (typically set in ``__init__``).
    The dispatcher in :mod:`gui.task._worker` injects the resolved
    (possibly cached) context as the argument to :meth:`run`.
    """

    context_type: ClassVar[type["Context"] | None] = None

    def __init__(self) -> None:
        self._context: "Context | None" = None

    @abstractmethod
    def run(self, context: "Context | None") -> T:
        """Execute the task.

        Args:
            context: The live context instance for this worker, or
                ``None`` if the task has no associated context.

        Returns:
            The task result, which must be picklable so it can be
            returned across the process boundary.
        """
