"""Optional Ultralytics YOLO detector adapter."""

from typing import Any

from scenechat.models import Detection


class YoloDetector:
    name = "yolo"

    def __init__(self, model_path: str, confidence: float):
        if not model_path:
            raise ValueError("DETECTOR_MODEL is required for the YOLO backend")
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("Install SceneChat with the 'yolo' optional dependency") from exc
        self._model = YOLO(model_path)
        self._confidence = confidence

    def detect(self, frame: Any) -> list[Detection]:
        height, width = frame.shape[:2]
        results = self._model.predict(frame, conf=self._confidence, verbose=False)
        detections: list[Detection] = []
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = (float(value) for value in box.xyxy[0].tolist())
                class_id = int(box.cls[0])
                detections.append(
                    Detection(
                        label=str(result.names[class_id]),
                        confidence=float(box.conf[0]),
                        x=max(0, x1 / width),
                        y=max(0, y1 / height),
                        width=min(1, x2 / width) - max(0, x1 / width),
                        height=min(1, y2 / height) - max(0, y1 / height),
                    )
                )
        return detections

