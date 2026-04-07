from __future__ import annotations

from dataclasses import dataclass

from .detection import Detection
from .tracking import TrackRegistry


@dataclass
class Zone:
    x1: int
    y1: int
    x2: int
    y2: int

    def contains_point(self, point: tuple[int, int]) -> bool:
        x, y = point
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2


def iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    iw = max(0, ix2 - ix1)
    ih = max(0, iy2 - iy1)
    inter = iw * ih
    if inter == 0:
        return 0.0

    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    return inter / max(1, area_a + area_b - inter)


@dataclass
class SuspiciousEvent:
    timestamp: float
    event_type: str
    track_id: int
    details: str


class RuleEngine:
    def __init__(
        self,
        track_registry: TrackRegistry,
        scan_zone: Zone,
        bagging_zone: Zone,
        no_scan_timeout_sec: float,
        hand_cover_overlap_threshold: float,
        swap_distance_threshold_px: float,
    ):
        self.tracks = track_registry
        self.scan_zone = scan_zone
        self.bagging_zone = bagging_zone
        self.no_scan_timeout_sec = no_scan_timeout_sec
        self.hand_cover_overlap_threshold = hand_cover_overlap_threshold
        self.swap_distance_threshold_px = swap_distance_threshold_px
        self.last_event_for_track: dict[tuple[int, str], float] = {}

    def evaluate(self, detections: list[Detection], timestamp: float) -> list[SuspiciousEvent]:
        events: list[SuspiciousEvent] = []
        track_state_map = self.tracks.update(detections, timestamp)

        hands = [d for d in detections if d.class_name == "person"]
        items = [d for d in detections if d.class_name != "person"]

        for det in items:
            track = track_state_map.get(det.track_id)
            if track is None:
                continue

            in_scan = self.scan_zone.contains_point(det.center)
            in_bagging = self.bagging_zone.contains_point(det.center)
            if in_scan:
                track.seen_in_scan_zone = True
                if track.scan_inferred_at is None and (timestamp - track.first_seen_ts) > 0.8:
                    track.scan_inferred_at = timestamp

            if in_bagging:
                track.seen_in_bagging_zone = True

            if track.seen_in_scan_zone and track.scan_inferred_at is None:
                if timestamp - track.first_seen_ts > self.no_scan_timeout_sec:
                    evt = SuspiciousEvent(
                        timestamp=timestamp,
                        event_type="no_scan_after_scan_zone_entry",
                        track_id=track.track_id,
                        details="Item in scan zone without inferred scan event within timeout",
                    )
                    if self._allow_event(evt):
                        events.append(evt)

            if in_scan and any(
                iou(det.bbox_xyxy, hand.bbox_xyxy) >= self.hand_cover_overlap_threshold
                for hand in hands
            ):
                evt = SuspiciousEvent(
                    timestamp=timestamp,
                    event_type="barcode_covered_by_hand",
                    track_id=track.track_id,
                    details="Item overlapped by person bbox while in scan zone",
                )
                if self._allow_event(evt):
                    events.append(evt)

            if track.seen_in_bagging_zone and not track.seen_in_scan_zone:
                evt = SuspiciousEvent(
                    timestamp=timestamp,
                    event_type="bypass_scan_zone",
                    track_id=track.track_id,
                    details="Item reached bagging zone without passing scan zone",
                )
                if self._allow_event(evt):
                    events.append(evt)

            if track.scan_inferred_at is not None and len(track.history) >= 2:
                prev_center = track.history[-2]
                if abs(det.center[0] - prev_center[0]) > self.swap_distance_threshold_px:
                    evt = SuspiciousEvent(
                        timestamp=timestamp,
                        event_type="item_swap_after_scan",
                        track_id=track.track_id,
                        details="Large post-scan displacement suggests potential item swap",
                    )
                    if self._allow_event(evt):
                        events.append(evt)

        return events

    def _allow_event(self, event: SuspiciousEvent) -> bool:
        key = (event.track_id, event.event_type)
        last_time = self.last_event_for_track.get(key)
        if last_time is not None and (event.timestamp - last_time) < 2.0:
            return False
        self.last_event_for_track[key] = event.timestamp
        return True
