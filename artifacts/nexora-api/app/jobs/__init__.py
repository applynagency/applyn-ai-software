"""Async job queue (Arq + Redis).

Public surface:

* ``submit`` (``app.jobs.submit``) — enqueue a job or run it inline.
* ``WorkerSettings`` (``app.jobs.worker``) — the Arq worker entrypoint:
  ``arq app.jobs.worker.WorkerSettings``.

All Arq imports are lazy so the API process boots without the package installed.
"""
