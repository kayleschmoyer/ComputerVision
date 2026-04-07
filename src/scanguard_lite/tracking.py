from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from .detection import Detection


@dataclass
class TrackState:
    track_id: int
    class_name: str
    last_center: tuple[int, int]
    history: deque[tuple[int, int]] = field(default_factory=lambda: deque(maxlen=30))
    first_seen_ts: float = 0.0
    last_seen_ts: float = 0.0
    seen_in_scan_zone: bool = False
    seen_in_bagging_zone: bool = False
    scan_inferred_at: float | None = None


class TrackRegistry:
    def __init__(self):
        self.tracks: dict[int, TrackState] = {}
        self.missing_count = defaultdict(int)

    def update(self, detections: list[Detection], timestamp: float) -> dict[int, TrackState]:
        active_ids = set()

        for det in detections:
            if det.track_id < 0:
                continue
            active_ids.add(det.track_id)
            if det.track_id not in self.tracks:
                self.tracks[det.track_id] = TrackState(
                    track_id=det.track_id,
                    class_name=det.class_name,
                    last_center=det.center,
                    first_seen_ts=timestamp,
                    last_seen_ts=timestamp,
                )

            track = self.tracks[det.track_id]
            track.class_name = det.class_name
            track.last_center = det.center
            track.last_seen_ts = timestamp
            track.history.append(det.center)
            self.missing_count[det.track_id] = 0

        for track_id in list(self.tracks.keys()):
            if track_id not in active_ids:
                self.missing_count[track_id] += 1
                if self.missing_count[track_id] > 60:
                    del self.tracks[track_id]
                    del self.missing_count[track_id]

        return self.tracks
