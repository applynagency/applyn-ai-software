#!/bin/bash
PORT="${PORT:-8001}"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --reload --log-level info
