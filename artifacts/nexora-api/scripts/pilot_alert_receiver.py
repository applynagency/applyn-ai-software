#!/usr/bin/env python3
"""Internal-only Alertmanager webhook receiver for Sprint 67G validation."""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

OUT_PATH = Path(os.environ.get("PILOT_ALERT_RECEIPT_PATH", "/data/alert-receiver-receipt.json"))
CHANNEL = os.environ.get("PILOT_ALERT_CHANNEL", "internal_webhook")
_lock = threading.Lock()
_state: dict[str, Any] = {
    "firing_events": [],
    "resolved_events": [],
    "firing_count": 0,
    "resolved_count": 0,
    "duplicate_prevented": True,
    "channel": CHANNEL,
    "rule_name": "CustomerPilotAlertDeliveryTest",
    "delivered": False,
}


def _redact_alert(alert: dict) -> dict:
    labels = alert.get("labels") or {}
    return {
        "status": alert.get("status"),
        "alertname": labels.get("alertname"),
        "severity": labels.get("severity"),
        "component": labels.get("component"),
        "starts_at": alert.get("startsAt") or alert.get("starts_at"),
        "ends_at": alert.get("endsAt") or alert.get("ends_at"),
    }


def _record_payload(payload: dict) -> None:
    alerts = payload.get("alerts") or []
    with _lock:
        seen_firing = {e.get("starts_at") for e in _state["firing_events"]}
        seen_resolved = {e.get("ends_at") for e in _state["resolved_events"]}
        for alert in alerts:
            item = _redact_alert(alert)
            status = (alert.get("status") or "").lower()
            if status == "firing":
                if item.get("starts_at") in seen_firing:
                    continue
                _state["firing_events"].append(item)
                _state["firing_count"] = len(_state["firing_events"])
                if not _state.get("fired_at"):
                    _state["fired_at"] = datetime.now(UTC).isoformat()
                if item.get("alertname"):
                    _state["rule_name"] = item["alertname"]
            elif status == "resolved":
                if item.get("ends_at") in seen_resolved:
                    continue
                _state["resolved_events"].append(item)
                _state["resolved_count"] = len(_state["resolved_events"])
                _state["resolved_at"] = datetime.now(UTC).isoformat()
        _state["duplicate_prevented"] = _state["firing_count"] <= 1
        _state["delivered"] = _state["firing_count"] >= 1 and _state["resolved_count"] >= 1
        _state["validated_at"] = datetime.now(UTC).isoformat()
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(_state, indent=2), encoding="utf-8")


def _reset_state() -> None:
    with _lock:
        _state.clear()
        _state.update({
            "firing_events": [],
            "resolved_events": [],
            "firing_count": 0,
            "resolved_count": 0,
            "duplicate_prevented": True,
            "channel": CHANNEL,
            "rule_name": "CustomerPilotAlertDeliveryTest",
            "delivered": False,
        })
        if OUT_PATH.is_file():
            OUT_PATH.unlink()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # pragma: no cover - quiet server
        return

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            body = json.dumps({"ok": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        if self.path.rstrip("/") == "/reset":
            _reset_state()
            self.send_response(200)
            self.end_headers()
            return
        if self.path.rstrip("/") != "/webhook":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return
        _record_payload(payload)
        self.send_response(200)
        self.end_headers()


def main() -> None:
    port = int(os.environ.get("PILOT_ALERT_RECEIVER_PORT", "9191"))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(json.dumps({"listening": port, "out": str(OUT_PATH)}), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
