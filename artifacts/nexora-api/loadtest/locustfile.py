"""Locust load profile for Nexora (Sprint 61B).

Optional alternative to ``run_load.py`` for distributed load generation and the
Locust web UI. Install locust (not a runtime dependency):

    pip install locust
    locust -f loadtest/locustfile.py --host http://localhost:8000

Set credentials via env LOAD_EMAIL / LOAD_PASSWORD.
"""

from __future__ import annotations

import os

from locust import HttpUser, between, task


class NexoraUser(HttpUser):
    wait_time = between(0.1, 1.0)

    def on_start(self) -> None:
        email = os.getenv("LOAD_EMAIL", "admin@example.com")
        password = os.getenv("LOAD_PASSWORD", "changeme")
        self.token = None
        resp = self.client.post("/v1/auth/login", json={"email": email, "password": password})
        if resp.status_code == 200:
            self.token = resp.json().get("access_token")

    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task(3)
    def discovery(self) -> None:
        self.client.get("/v1/discovery/summary", headers=self._headers, name="discovery")

    @task(3)
    def dashboard(self) -> None:
        self.client.get("/v1/reliability/dashboard", headers=self._headers, name="dashboard")

    @task(2)
    def copilot(self) -> None:
        self.client.post("/v1/copilot/sessions", json={}, headers=self._headers, name="copilot")

    @task(1)
    def api_keys(self) -> None:
        self.client.get("/v1/api-keys", headers=self._headers, name="api_keys")

    @task(1)
    def war_room(self) -> None:
        self.client.get("/v1/war-room/incidents", headers=self._headers, name="war_room")

    @task(1)
    def incidents(self) -> None:
        self.client.get("/v1/incidents", headers=self._headers, name="incidents")
