from __future__ import annotations

import logging
import time

import cv2

from .config import load_config
from .detection import VideoSource, YOLODetector, draw_detections
from .events import AlertPayload, AlertPublisher, ClipRecorder
from .rules import RuleEngine, Zone
from .tracking import TrackRegistry


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def draw_zone(frame, zone: Zone, label: str, color=(255, 200, 0)):
    cv2.rectangle(frame, (zone.x1, zone.y1), (zone.x2, zone.y2), color, 2)
    cv2.putText(
        frame,
        label,
        (zone.x1, max(20, zone.y1 - 10)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        color,
        2,
    )


def main() -> None:
    setup_logging()
    logger = logging.getLogger("scanguard.cv")

    cfg = load_config()
    video = VideoSource(
        source=cfg.camera["source"],
        width=cfg.camera["width"],
        height=cfg.camera["height"],
        fps=cfg.camera["fps"],
    )
    detector = YOLODetector(
        model_path=cfg.model["yolo_model"],
        tracker_cfg=cfg.model["tracker"],
        conf=cfg.model["conf_threshold"],
        iou=cfg.model["iou_threshold"],
    )
    track_registry = TrackRegistry()

    scan_cfg = cfg.zones["scan_zone"]
    bag_cfg = cfg.zones["bagging_zone"]
    scan_zone = Zone(**scan_cfg)
    bagging_zone = Zone(**bag_cfg)

    rules = RuleEngine(
        track_registry=track_registry,
        scan_zone=scan_zone,
        bagging_zone=bagging_zone,
        no_scan_timeout_sec=cfg.rules["no_scan_timeout_sec"],
        hand_cover_overlap_threshold=cfg.rules["hand_cover_overlap_threshold"],
        swap_distance_threshold_px=cfg.rules["swap_distance_threshold_px"],
    )

    clip_recorder = ClipRecorder(
        storage_dir=cfg.events["storage_dir"],
        clip_duration_sec=cfg.events["clip_duration_sec"],
        fps=cfg.camera["fps"],
    )
    publisher = AlertPublisher(
        api_post_url=cfg.events["api_post_url"],
        enabled=cfg.events["send_to_api"],
    )

    classes_of_interest = set(cfg.model.get("classes_of_interest", []))

    logger.info("Starting ScanGuard Lite CV loop")

    while True:
        ok, frame = video.read()
        if not ok:
            logger.warning("Unable to read frame from camera source")
            time.sleep(0.2)
            continue

        ts = time.time()
        clip_recorder.add_frame(frame, ts)
        detections = detector.detect_and_track(frame)
        if classes_of_interest:
            detections = [d for d in detections if d.class_name in classes_of_interest]
        events = rules.evaluate(detections, ts)

        for event in events:
            try:
                clip_path = clip_recorder.save_recent_clip(cfg.camera["id"], event.event_type)
            except RuntimeError:
                logger.warning("Skipping event because clip buffer was empty")
                continue

            payload = AlertPayload(
                timestamp=event.timestamp,
                event_type=event.event_type,
                clip_path=clip_path,
                camera_id=cfg.camera["id"],
                details=event.details,
            )
            logger.warning("Suspicious event detected: %s", payload)
            publisher.publish(payload)

        vis = draw_detections(frame, detections)
        draw_zone(vis, scan_zone, "Scan Zone", (0, 255, 255))
        draw_zone(vis, bagging_zone, "Bagging Zone", (255, 0, 255))

        cv2.imshow("ScanGuard Lite", vis)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    video.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
