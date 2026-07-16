"""Promptable, offline YOLOE detector adapter."""

import threading
from pathlib import Path
from typing import Any

from scenechat.models import Detection


class YoloEDetector:
    name = "yoloe"

    def __init__(
        self,
        model_path: str,
        text_encoder_path: str,
        confidence: float,
        prompts: list[str],
    ):
        if not Path(model_path).is_file():
            raise ValueError("DETECTOR_MODEL must identify a downloaded YOLOE checkpoint")
        if not Path(text_encoder_path).is_file():
            raise ValueError("DETECTOR_TEXT_ENCODER must identify a downloaded text encoder")
        try:
            from ultralytics import YOLOE
        except ImportError as exc:
            raise RuntimeError("Install SceneChat with the 'yoloe' optional dependency") from exc

        self._model = YOLOE(model_path)
        self._text_encoder_path = text_encoder_path
        self._confidence = confidence
        self._lock = threading.Lock()
        self._prompts: tuple[str, ...] = ()
        self.set_prompts(prompts)

    @property
    def prompts(self) -> list[str]:
        with self._lock:
            return list(self._prompts)

    def set_prompts(self, prompts: list[str]) -> None:
        """Encode approved text prompts locally and apply them atomically."""
        requested = tuple(prompts)
        with self._lock:
            if requested == self._prompts:
                return
            try:
                import torch
                from ultralytics.nn.text_model import MobileCLIPTS
            except ImportError as exc:
                raise RuntimeError("The YOLOE text encoder dependency is not installed") from exc

            inner = self._model.model
            device = next(inner.parameters()).device
            with torch.inference_mode():
                encoder = MobileCLIPTS(device, self._text_encoder_path)
                tokens = encoder.tokenize(list(requested))
                features = encoder.encode_text(tokens).reshape(1, len(requested), -1)
                embeddings = inner.model[-1].get_tpe(features)
                self._model.set_classes(list(requested), embeddings)
            self._prompts = requested

    def detect(self, frame: Any) -> list[Detection]:
        height, width = frame.shape[:2]
        with self._lock:
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
