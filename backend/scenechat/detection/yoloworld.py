"""Promptable, offline YOLO-World detector adapter."""

import os
import threading
from pathlib import Path
from typing import Any

from scenechat.detection.base import normalise_box
from scenechat.models import Detection


class YoloWorldDetector:
    name = "yoloworld"

    def __init__(
        self,
        model_path: str,
        clip_path: str,
        confidence: float,
        prompts: list[str],
    ):
        if not Path(model_path).is_file():
            raise ValueError(
                "DETECTOR_MODEL must identify a downloaded YOLO-World checkpoint"
            )
        clip_file = Path(clip_path)
        if not clip_file.is_file() or clip_file.name != "ViT-B-32.pt":
            raise ValueError(
                "DETECTOR_YOLOWORLD_CLIP must identify a local ViT-B-32.pt file"
            )
        try:
            from ultralytics import YOLOWorld
        except ImportError as exc:
            raise RuntimeError(
                "Install SceneChat with the 'yoloworld' optional dependency"
            ) from exc

        self._model = YOLOWorld(model_path)
        self._clip_cache = str(clip_file.parent)
        self._confidence = confidence
        self._lock = threading.Lock()
        self._prompts: tuple[str, ...] = ()
        self.set_prompts(prompts)

    @property
    def prompts(self) -> list[str]:
        with self._lock:
            return list(self._prompts)

    def set_prompts(self, prompts: list[str]) -> None:
        """Encode approved prompts locally and apply them between inference passes."""
        requested = tuple(prompts)
        with self._lock:
            if requested == self._prompts:
                return
            previous_cache = os.environ.get("CLIP_CACHE_DIR")
            os.environ["CLIP_CACHE_DIR"] = self._clip_cache
            try:
                self._model.set_classes(list(requested))
            finally:
                if previous_cache is None:
                    os.environ.pop("CLIP_CACHE_DIR", None)
                else:
                    os.environ["CLIP_CACHE_DIR"] = previous_cache
            self._prompts = requested

    def detect(self, frame: Any) -> list[Detection]:
        height, width = frame.shape[:2]
        with self._lock:
            results = self._model.predict(frame, conf=self._confidence, verbose=False)
        detections: list[Detection] = []
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = (float(value) for value in box.xyxy[0].tolist())
                normalised = normalise_box(x1, y1, x2, y2, width, height)
                if normalised is None:
                    continue
                class_id = int(box.cls[0])
                detections.append(
                    Detection(
                        label=str(result.names[class_id]),
                        confidence=float(box.conf[0]),
                        x=normalised[0],
                        y=normalised[1],
                        width=normalised[2],
                        height=normalised[3],
                    )
                )
        return detections
