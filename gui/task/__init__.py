"""Task system public API.

Usage::

    from gui.task import Context, Task, submit, release_context

The persistent worker pool is created lazily on the first call to
:func:`submit` or :func:`release_context`.
"""

from __future__ import annotations

import atexit
import os
from multiprocessing import Pool
from multiprocessing.pool import AsyncResult
from typing import Any, Callable

from .context import Context
from .task import Task
from ._worker import _run_task, _release_context

__all__ = ["Context", "Task", "submit", "release_context"]

#region Persistent worker pool
# Created lazily to avoid re-spawning inside worker processes that import
# this module while unpickling a Task.

_pool: Pool | None = None

def _get_pool() -> Pool:
    """Return the shared pool, creating it on the first call."""
    global _pool
    if _pool is None:
        _pool = Pool(os.cpu_count())
        atexit.register(_pool.terminate)
    return _pool

#endregion

#region Public helpers

def submit(
    task: Task,
    callback: Callable[[Any], None] | None = None,
    error_callback: Callable[[BaseException], None] | None = None,
) -> AsyncResult:
    """Submit *task* for execution in a worker process.

    The task's context (if any) is lazily set up inside the worker on
    first use; see :mod:`gui.task._worker` for details.

    Args:
        task: Any :class:`Task` subclass instance.  Must be picklable.
        callback: Called in the main process with the return value when
            the task succeeds.
        error_callback: Called in the main process with the exception
            when the task raises.

    Returns:
        An :class:`~multiprocessing.pool.AsyncResult` handle.
    """
    return _get_pool().apply_async(
        _run_task,
        args=(task,),
        callback=callback,
        error_callback=error_callback,
    )

def release_context(ctx: Context) -> None:
    """Fan out teardown for *ctx* to all worker processes.

    Calls :func:`~gui.task._worker._release_context` on every worker via
    ``pool.map``.  Workers that never cached this context UUID ignore the
    call silently.

    This is a **best-effort** synchronous operation: ``pool.map`` with
    ``cpu_count`` tasks does not guarantee exactly one call per physical
    worker, but is sufficient for cleanup of stateless resources.

    Args:
        ctx: The context to release.  Its ``teardown()`` will be invoked
            in each worker that holds a cached copy.
    """
    n = os.cpu_count() or 1
    _get_pool().map(_release_context, [ctx.uuid] * n)

#endregion
