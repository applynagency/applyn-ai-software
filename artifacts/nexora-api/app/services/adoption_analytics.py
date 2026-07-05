"""Sprint 57A — Adoption Analytics.

Measures customer success from a stream of usage events so the platform can show
where customers struggle. It tracks seven event types:

    guide_view, tour_start, tour_complete, academy_progress,
    video_view, doc_search, feature_use

From those it computes four scores — Adoption, Documentation, Training, and an
overall Success score — and a dashboard surfacing the most- and least-used
features, drop-off points, and customer health.

Deterministic and stateless: callers pass an event list (or use the built-in
representative dataset). No DB.
"""

from __future__ import annotations

import math
from typing import Any

from app.services.customer_success_academy import CustomerSuccessAcademy
from app.services.customer_success_content import MODULES
from app.services.product_tour_engine import ProductTourEngine
from app.services.video_training import VideoTrainingEngine

EVENT_TYPES = [
    "guide_view", "tour_start", "tour_complete", "academy_progress",
    "video_view", "doc_search", "feature_use",
]

# How many uses of a feature counts as "fully adopted" for depth scoring.
_DEPTH_TARGET = 8


def _band(score: int) -> str:
    if score >= 80:
        return "Healthy"
    if score >= 60:
        return "Fair"
    if score >= 40:
        return "At Risk"
    return "Critical"


def _ev(etype: str, target: str, value: int = 1) -> dict[str, Any]:
    return {"type": etype, "target": target, "value": value}


class AdoptionAnalyticsEngine:
    def __init__(self) -> None:
        self._tours: list[dict[str, Any]] | None = None
        self._tracks: list[dict[str, Any]] | None = None
        self._videos: list[str] | None = None

    # ------------------------------------------------------- catalog
    def _features(self) -> list[dict[str, str]]:
        return [{"key": m["key"], "name": m["name"], "route": m["route"]} for m in MODULES]

    def _tour_keys(self) -> list[dict[str, Any]]:
        if self._tours is None:
            self._tours = ProductTourEngine().all_tours()
        return self._tours

    def _track_keys(self) -> list[dict[str, Any]]:
        if self._tracks is None:
            self._tracks = CustomerSuccessAcademy().tracks()
        return self._tracks

    def _video_ids(self) -> list[str]:
        if self._videos is None:
            self._videos = [v["id"] for v in VideoTrainingEngine().library()["items"]]
        return self._videos

    # ------------------------------------------------------- representative dataset
    def sample_events(self) -> list[dict[str, Any]]:
        """A deterministic, representative event stream with clear strong and weak
        spots so the dashboard always demonstrates where customers struggle."""
        events: list[dict[str, Any]] = []
        feats = self._features()
        n = len(feats)
        for i, f in enumerate(feats):
            weight = n - i  # 18 .. 1 — earlier modules are more popular
            events += [_ev("guide_view", f["key"]) for _ in range(weight)]
            # The last four features are never adopted (clear "least used").
            uses = max(0, weight - 4) * 2
            events += [_ev("feature_use", f["key"]) for _ in range(uses)]
            events += [_ev("video_view", f"{f['key']}-overview") for _ in range(math.ceil(weight / 2))]

        for i, t in enumerate(self._tour_keys()):
            starts = max(1, 12 - i)
            completes = max(0, starts - (i * 2 + 1))  # later tours drop off hard
            events += [_ev("tour_start", t["key"]) for _ in range(starts)]
            events += [_ev("tour_complete", t["key"]) for _ in range(completes)]

        for i, track in enumerate(self._track_keys()):
            pct = max(0, 100 - i * 25)  # 100, 75, 50, 25, 0
            events.append(_ev("academy_progress", track["key"], value=pct))

        searches = [
            ("how to create an slo", 1), ("rollback a deployment", 1),
            ("investigate cost anomaly", 1), ("export a postmortem", 1),
            ("capacity forecast", 1), ("set up ai teams", 0),
            ("change failure api", 0), ("incident webhook", 0),
        ]
        for query, resolved in searches:
            events += [_ev("doc_search", query, value=resolved) for _ in range(3)]
        return events

    # ------------------------------------------------------- aggregation
    def _aggregate(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        agg: dict[str, dict[str, int]] = {et: {} for et in EVENT_TYPES}
        academy_pct: dict[str, int] = {}
        searches_total = 0
        searches_resolved = 0
        for e in events:
            etype = e.get("type")
            if etype not in agg:
                continue
            target = str(e.get("target", ""))
            value = int(e.get("value", 1) or 0)
            if etype == "academy_progress":
                academy_pct[target] = max(academy_pct.get(target, 0), value)
                continue
            if etype == "doc_search":
                searches_total += 1
                searches_resolved += 1 if value else 0
            agg[etype][target] = agg[etype].get(target, 0) + 1
        return {
            "agg": agg,
            "academy_pct": academy_pct,
            "searches_total": searches_total,
            "searches_resolved": searches_resolved,
        }

    # ------------------------------------------------------- scores
    def _scores(self, data: dict[str, Any]) -> dict[str, int]:
        agg = data["agg"]
        feats = self._features()
        total_features = len(feats)
        total_videos = len(self._video_ids())

        # Documentation: breadth of guides viewed + search resolution.
        guides_viewed = len(agg["guide_view"])
        coverage = guides_viewed / total_features if total_features else 0
        if data["searches_total"]:
            search_success = data["searches_resolved"] / data["searches_total"]
            documentation = round(100 * (0.7 * coverage + 0.3 * search_success))
        else:
            documentation = round(100 * coverage)

        # Training: tour completion rate + video coverage + academy progress.
        starts = sum(agg["tour_start"].values())
        completes = sum(agg["tour_complete"].values())
        completion_rate = completes / starts if starts else 0
        videos_viewed = len(agg["video_view"])
        video_coverage = videos_viewed / total_videos if total_videos else 0
        academy_vals = list(data["academy_pct"].values())
        academy_avg = (sum(academy_vals) / len(academy_vals) / 100) if academy_vals else 0
        training_parts = [completion_rate, video_coverage, academy_avg]
        training = round(100 * (sum(training_parts) / len(training_parts)))

        # Adoption: breadth + depth of feature use.
        features_used = len(agg["feature_use"])
        breadth = features_used / total_features if total_features else 0
        total_uses = sum(agg["feature_use"].values())
        depth = min(1.0, total_uses / (total_features * _DEPTH_TARGET)) if total_features else 0
        adoption = round(100 * (0.6 * breadth + 0.4 * depth))

        success = round(0.35 * adoption + 0.35 * training + 0.30 * documentation)
        return {
            "adoption_score": adoption,
            "documentation_score": documentation,
            "training_score": training,
            "success_score": success,
        }

    # ------------------------------------------------------- feature usage ranking
    def _feature_usage(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        agg = data["agg"]
        rows: list[dict[str, Any]] = []
        for f in self._features():
            key = f["key"]
            guide_views = agg["guide_view"].get(key, 0)
            feature_uses = agg["feature_use"].get(key, 0)
            video_views = sum(c for t, c in agg["video_view"].items() if t.startswith(f"{key}-"))
            usage_score = feature_uses * 2 + guide_views + video_views
            rows.append({
                "key": key,
                "name": f["name"],
                "route": f["route"],
                "guide_views": guide_views,
                "feature_uses": feature_uses,
                "video_views": video_views,
                "usage_score": usage_score,
            })
        rows.sort(key=lambda r: (-r["usage_score"], r["name"]))
        return rows

    # ------------------------------------------------------- drop-off points
    def _drop_off(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        agg = data["agg"]
        points: list[dict[str, Any]] = []

        # Tours started but not completed.
        for t in self._tour_keys():
            starts = agg["tour_start"].get(t["key"], 0)
            completes = agg["tour_complete"].get(t["key"], 0)
            if starts > 0 and completes < starts:
                rate = completes / starts
                if rate < 0.6:
                    points.append({
                        "entity": t["key"],
                        "label": t.get("name", t["key"]),
                        "type": "tour",
                        "reached": starts,
                        "converted": completes,
                        "drop_off_rate": round((1 - rate) * 100),
                        "detail": "Customers start this tour but abandon it before finishing.",
                    })

        # Academy tracks left partially complete.
        for track in self._track_keys():
            pct = data["academy_pct"].get(track["key"])
            if pct is not None and 0 < pct < 100:
                points.append({
                    "entity": track["key"],
                    "label": track.get("title", track["key"]),
                    "type": "academy",
                    "reached": 100,
                    "converted": pct,
                    "drop_off_rate": 100 - pct,
                    "detail": "This learning track is started but not completed.",
                })

        # Features read about but never used.
        for f in self._features():
            guide_views = agg["guide_view"].get(f["key"], 0)
            feature_uses = agg["feature_use"].get(f["key"], 0)
            if guide_views >= 3 and feature_uses == 0:
                points.append({
                    "entity": f["key"],
                    "label": f["name"],
                    "type": "feature",
                    "reached": guide_views,
                    "converted": 0,
                    "drop_off_rate": 100,
                    "detail": "Customers read the guide but never use the feature.",
                })

        points.sort(key=lambda p: (-p["drop_off_rate"], -p["reached"]))
        return points

    # ------------------------------------------------------- customer health
    def _health(self, scores: dict[str, int], data: dict[str, Any], drop_offs: list[dict[str, Any]]) -> dict[str, Any]:
        success = scores["success_score"]
        signals: list[str] = []
        agg = data["agg"]
        starts = sum(agg["tour_start"].values())
        completes = sum(agg["tour_complete"].values())
        if starts and completes / starts < 0.6:
            signals.append("Low tour completion rate")
        unused = sum(1 for f in self._features() if agg["feature_use"].get(f["key"], 0) == 0)
        if unused:
            signals.append(f"{unused} features never used")
        if data["searches_total"]:
            unresolved = data["searches_total"] - data["searches_resolved"]
            if unresolved:
                signals.append(f"{unresolved} documentation searches returned nothing useful")
        partial_tracks = sum(1 for t in self._track_keys()
                             if 0 < data["academy_pct"].get(t["key"], 0) < 100)
        if partial_tracks:
            signals.append(f"{partial_tracks} academy tracks abandoned mid-way")
        return {
            "status": _band(success),
            "success_score": success,
            "risk_signals": signals,
            "top_struggle": drop_offs[0]["label"] if drop_offs else None,
        }

    # ------------------------------------------------------- public API
    def analyze(self, events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        events = events if events else self.sample_events()
        data = self._aggregate(events)
        agg = data["agg"]
        scores = self._scores(data)
        usage = self._feature_usage(data)
        drop_offs = self._drop_off(data)
        health = self._health(scores, data, drop_offs)
        counts = {
            "guide_views": sum(agg["guide_view"].values()),
            "tour_starts": sum(agg["tour_start"].values()),
            "tour_completions": sum(agg["tour_complete"].values()),
            "academy_tracks_tracked": len(data["academy_pct"]),
            "academy_average_progress": (
                round(sum(data["academy_pct"].values()) / len(data["academy_pct"]))
                if data["academy_pct"] else 0
            ),
            "video_views": sum(agg["video_view"].values()),
            "documentation_searches": data["searches_total"],
            "feature_adoptions": sum(agg["feature_use"].values()),
            "events_analyzed": len(events),
        }
        return {
            "scores": scores,
            "counts": counts,
            "most_used_features": usage[:5],
            "least_used_features": list(reversed(usage[-5:])),
            "drop_off_points": drop_offs,
            "customer_health": health,
            "event_types": EVENT_TYPES,
        }
