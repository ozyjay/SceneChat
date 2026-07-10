#!/usr/bin/env python3
"""Send one local image to the configured vLLM adapter and report latency."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from scenechat.config import Settings
from scenechat.vision.vllm import VllmGemmaProvider


async def run(image_path: Path, question: str) -> int:
    settings = Settings(vision_provider="vllm")
    provider = VllmGemmaProvider(
        settings.vllm_base_url,
        settings.vllm_api_key,
        settings.vllm_model,
        settings.vision_request_timeout_seconds,
    )
    try:
        if not await provider.health():
            print("vLLM model endpoint is unavailable.", file=sys.stderr)
            return 2
        result = await provider.analyse_scene(image_path.read_bytes(), question)
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return 0
    finally:
        await provider.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--question", default="Describe the scene.")
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error(f"image does not exist: {args.image}")
    return asyncio.run(run(args.image, args.question))


if __name__ == "__main__":
    raise SystemExit(main())

