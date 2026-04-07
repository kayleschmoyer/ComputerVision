from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import cv2
import numpy as np
from ultralytics import YOLO


@dataclass
class Detection:
    track_id: int
    class_name: str
    confidence: float
    bbox_xyxy: tuple[int, int, int, int]

    @property
    def center(self) -> tuple[int, int]:
        x1, y1, x2, y2 = self.bbox_xyxy
        return ((x1 + x2) // 2, (y1 + y2) // 2)


class VideoSource:
    def __init__(self, source: str | int, width: int, height: int, fps: int):
        if isinstance(source, str) and source.isdigit():
            source = int(source)
        self.cap = cv2.VideoCapture(source)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)

    def read(self):
        return self.cap.read()

    def release(self) -> None:
        self.cap.release()


class YOLODetector:
    def __init__(self, model_path: str, tracker_cfg: str, conf: float, iou: float):
        self.model = YOLO(model_path)
        self.tracker_cfg = tracker_cfg
        self.conf = conf
        self.iou = iou

    def detect_and_track(self, frame: np.ndarray) -> list[Detection]:
        result = self.model.track(
            frame,
            persist=True,
            tracker=self.tracker_cfg,
            conf=self.conf,
            iou=self.iou,
            verbose=False,
        )[0]
        detections: list[Detection] = []

        if result.boxes is None:
            return detections

        for box in result.boxes:
            track_id = int(box.id.item()) if box.id is not None else -1
            cls_id = int(box.cls.item())
            class_name = self.model.names.get(cls_id, str(cls_id))
            conf = float(box.conf.item())
            xyxy = tuple(int(v) for v in box.xyxy[0].tolist())
            detections.append(
                Detection(
                    track_id=track_id,
                    class_name=class_name,
                    confidence=conf,
                    bbox_xyxy=xyxy,
                )
            )
        return detections


def draw_detections(frame: np.ndarray, detections: Iterable[Detection]) -> np.ndarray:
    annotated = frame.copy()
    for det in detections:
        x1, y1, x2, y2 = det.bbox_xyxy
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (60, 200, 80), 2)
        label = f"{det.class_name}#{det.track_id} {det.confidence:.2f}"
        cv2.putText(
            annotated,
            label,
            (x1, max(10, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (60, 200, 80),
            2,
        )
    return annotated
