#!/usr/bin/env python3
"""Benchmark explicitly supplied YOLO models on local video without downloading assets."""

import argparse
import statistics
import time
from pathlib import Path


def benchmark(video: Path, model_path: str, frame_limit: int) -> None:
    try:
        import cv2
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("Install the 'yolo' optional dependency before benchmarking.") from exc
    model = YOLO(model_path)
    capture = cv2.VideoCapture(str(video))
    durations: list[float] = []
    count = 0
    while count < frame_limit:
        ok, frame = capture.read()
        if not ok:
            break
        started = time.perf_counter()
        model.predict(frame, verbose=False)
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
    args = parser.parse_args()
    for model in args.models:
        benchmark(args.video, model, args.frames)


if __name__ == "__main__":
    main()
