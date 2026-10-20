"""Background jobs (thread pool) so long renders never block the API or the UI."""
from __future__ import annotations

import logging
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger("naturemask.jobs")
_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="nm-job")
_JOBS: dict = {}
_LOCK = threading.Lock()


def submit(kind: str, fn, *args, **kwargs) -> str:
    jid = uuid.uuid4().hex[:12]
    job = {"id": jid, "kind": kind, "status": "queued", "progress": 0.0, "message": "Queued", "result": None,
           "error": None, "started": time.time(), "finished": None}
    with _LOCK:
        _JOBS[jid] = job

    def progress(p, msg=""):
        job["progress"] = float(max(0.0, min(1.0, p)))
        if msg:
            job["message"] = msg

    def run():
        job["status"] = "running"
        try:
            job["result"] = fn(*args, progress=progress, **kwargs)
            job["status"] = "done"
            job["progress"] = 1.0
            job["message"] = "Done"
        except Exception as e:  # report to the UI, keep the full trace in the log
            log.error("job %s (%s) failed: %s\n%s", jid, kind, e, traceback.format_exc())
            job["status"] = "error"
            job["error"] = str(e)
        finally:
            job["finished"] = time.time()

    _POOL.submit(run)
    return jid


def get(jid: str) -> dict:
    with _LOCK:
        if jid not in _JOBS:
            raise KeyError(jid)
        j = dict(_JOBS[jid])
    return j
