#!/usr/bin/env python3
"""Benchmark explicitly supplied promptable detectors without downloading assets."""

import argparse
import statistics
import time
from pathlib import Path


def create_benchmark_detector(
    model_path: str,
    text_encoder: str,
    yoloworld_clip: str,
    prompts: list[str],
    confidence: float,
):
    try:
        if Path(model_path).name.startswith("yoloe-"):
            if not text_encoder:
                raise SystemExit("--text-encoder is required when benchmarking YOLOE")
            from scenechat.detection.yoloe import YoloEDetector

            return YoloEDetector(model_path, text_encoder, confidence, prompts)
        if "world" in Path(model_path).stem.lower():
            if not yoloworld_clip:
                raise SystemExit(
                    "--yoloworld-clip is required when benchmarking YOLO-World"
                )
            from scenechat.detection.yoloworld import YoloWorldDetector

            return YoloWorldDetector(model_path, yoloworld_clip, confidence, prompts)
        raise SystemExit(
            f"Unsupported detector checkpoint {model_path}; use YOLOE or YOLO-World"
        )
    except ImportError as exc:
        raise SystemExit(
            "Install the matching 'yoloe' or 'yoloworld' optional dependency first."
        ) from exc


def benchmark(
    video: Path,
    model_path: str,
    frame_limit: int,
    text_encoder: str,
    yoloworld_clip: str,
    prompts: list[str],
    confidence: float,
) -> None:
    import cv2

    detector = create_benchmark_detector(
        model_path, text_encoder, yoloworld_clip, prompts, confidence
    )
    capture = cv2.VideoCapture(str(video))
    durations: list[float] = []
    count = 0
    while count < frame_limit:
        ok, frame = capture.read()
        if not ok:
            break
        started = time.perf_counter()
        detector.detect(frame)
        durations.append(time.perf_counter() - started)
        count += 1
    capture.release()
    if not durations:
        raise SystemExit(f"No frames read from {video}")
    mean = statistics.mean(durations)
    p95 = sorted(durations)[min(len(durations) - 1, int(len(durations) * 0.95))]
    print(f"{model_path}: {1 / mean:.2f} mean FPS, {p95 * 1000:.1f} ms p95, {count} frames")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("models", nargs="+", help="At least two local model paths are recommended")
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--text-encoder", default="", help="Local MobileCLIP2 file for YOLOE")
    parser.add_argument(
        "--yoloworld-clip",
        default="",
        help="Local ViT-B/32 weights file for YOLO-World",
    )
    parser.add_argument(
        "--prompts",
        nargs="+",
        default=["person", "camera", "laptop", "chair"],
    )
    parser.add_argument("--confidence", type=float, default=0.4)
    args = parser.parse_args()
    for model in args.models:
        benchmark(
            args.video,
            model,
            args.frames,
            args.text_encoder,
            args.yoloworld_clip,
            args.prompts,
            args.confidence,
        )


if __name__ == "__main__":
    main()
