from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
import requests


@dataclass
class AlertPayload:
    timestamp: float
    event_type: str
    clip_path: str
    camera_id: str
    details: str


class ClipRecorder:
    def __init__(self, storage_dir: str, clip_duration_sec: int, fps: int):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.clip_duration_sec = clip_duration_sec
        self.fps = max(1, fps)
        self.buffer: deque[tuple[float, np.ndarray]] = deque(maxlen=self.clip_duration_sec * self.fps)

    def add_frame(self, frame: np.ndarray, timestamp: float) -> None:
        self.buffer.append((timestamp, frame.copy()))

    def save_recent_clip(self, camera_id: str, event_type: str) -> str:
        if not self.buffer:
            raise RuntimeError("Clip buffer is empty")

        clip_id = f"{camera_id}_{event_type}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        clip_path = self.storage_dir / f"{clip_id}.mp4"
        _, first_frame = self.buffer[0]
        height, width = first_frame.shape[:2]
        writer = cv2.VideoWriter(
            str(clip_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            self.fps,
            (width, height),
        )

        for _, frame in self.buffer:
            writer.write(frame)
        writer.release()

        return str(clip_path)


class AlertPublisher:
    def __init__(self, api_post_url: str, enabled: bool = True):
        self.api_post_url = api_post_url
        self.enabled = enabled
        self.logger = logging.getLogger("scanguard.alerts")

    def publish(self, payload: AlertPayload) -> None:
        if not self.enabled:
            self.logger.info("Alert publishing disabled: %s", payload.event_type)
            return

        try:
            response = requests.post(self.api_post_url, json=asdict(payload), timeout=3)
            response.raise_for_status()
        except Exception as exc:
            self.logger.error("Failed to POST alert: %s", exc)
