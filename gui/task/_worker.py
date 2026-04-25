"""Worker-side dispatcher for the task system.

This module must contain only module-level, top-level callables so that
``multiprocessing`` can pickle them regardless of the start method
(``spawn`` on Windows and macOS, ``fork`` on Linux).

Importing ``gui.task`` or any Qt module here would re-create the process
pool inside each worker, causing infinite recursion.  Keep imports lean
and Qt-free.
"""

from __future__ import annotations

from typing import Any

# Per-process cache: uuid -> live Context instance.
# Each worker process has its own copy; values are never sent back to the
# main process.
_worker_context_cache: dict[str, Any] = {}

def _run_task(task: Any) -> Any:
    """Execute *task* inside a worker process, injecting its context.

    If the task carries a ``_context`` reference:

    1. The first time this worker sees the context UUID, ``setup()`` is
       called on the (already-pickled, freshly-deserialized) context
       object and the result is stored in the local cache.
    2. On subsequent calls the cached instance is reused — ``setup()``
       is **not** called again.

    Args:
        task: Any :class:`~gui.task.task.Task` subclass instance.

    Returns:
        Whatever ``task.run(context)`` returns.
    """
    context = None

    if task._context is not None:
        uuid = task._context.uuid
        if uuid not in _worker_context_cache:
            task._context.setup()
            _worker_context_cache[uuid] = task._context
        context = _worker_context_cache[uuid]

    return task.run(context)

def _release_context(uuid: str) -> None:
    """Tear down and evict the cached context identified by *uuid*.

    A no-op if this worker never cached the context (e.g. it never
    processed a task that needed it).

    Args:
        uuid: The UUID string of the context to release.
    """
    ctx = _worker_context_cache.pop(uuid, None)
    if ctx is not None:
        ctx.teardown()
