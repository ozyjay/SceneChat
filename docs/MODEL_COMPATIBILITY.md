# Model and hardware compatibility record

Last updated: 10 July 2026. Measurements marked **not run** must be completed on the actual booth session, outside the restricted development sandbox.

## Inspected environment

| Item | Observed |
|---|---|
| OS | Fedora Linux 44 Workstation |
| Host Python | 3.14.6 through pyenv; vLLM ROCm recipe calls for Python 3.12 |
| GPU | AMD Strix Halo, reported as Radeon 8050S/8060S graphics |
| System memory | 125 GiB total, 117 GiB available during inspection |
| ROCm packages | Fedora ROCm 7.1.x packages installed |
| GPU access in inspection sandbox | `/dev/kfd` unavailable; `rocminfo` could not enumerate an agent |
| Camera | no `/dev/video*` device exposed |
| Containers | Docker 29.6.1 installed; Docker socket denied; Podman runtime directory read-only |
| Relevant ports | 3900, 8900, and 8000 had no listener |

The container image, vLLM version, loaded model, GPU memory use, and latency could not be inspected through the restricted sockets. They are unresolved rather than assumed.

## Verified current Gemma 4 identifiers and modalities

Official current instruction-tuned model identifiers include:

- `google/gemma-4-E2B-it` — image, text, and audio; 5.1B total parameters including embeddings
- `google/gemma-4-E4B-it` — image, text, and audio; 8B total parameters including embeddings
- `google/gemma-4-12B-it` — unified image, text, audio, and video model
- `google/gemma-4-26B-A4B-it` — image and text MoE model
- `google/gemma-4-31B-it` — image and text dense model

Sources: [Hugging Face Gemma 4 release and checkpoint table](https://huggingface.co/blog/gemma4), [Google Gemma 4 12B model card](https://huggingface.co/google/gemma-4-12B), and [official vLLM Gemma 4 recipe](https://github.com/vllm-project/recipes/blob/main/Google/Gemma4.md).

All listed variants accept images. The selected compatibility candidate is **exactly `google/gemma-4-E2B-it`** because it minimises the initial resource risk. No other model has been silently substituted. Production selection remains pending hardware results.

## vLLM findings

vLLM 0.19.0 introduced full Gemma 4 multimodal support and requires `transformers>=5.5.0`. The official recipe documents OpenAI-compatible API use, a ROCm container `vllm/vllm-openai-rocm:latest`, and image input. Current recipes list AMD MI300X/MI325X/MI350X/MI355X as supported BF16 targets; they do **not** list Strix Halo. Therefore model fit in system memory does not establish kernel compatibility. Sources: [vLLM releases](https://github.com/vllm-project/vllm/releases) and [Gemma 4 recipe](https://github.com/vllm-project/recipes/blob/main/Google/Gemma4.md).

Approximate BF16 weights alone are about 10.2 GB for E2B and 16 GB for E4B, derived from their documented total parameter counts. Runtime memory is higher because of vision/audio encoders, KV cache, activations, allocator overhead, and the detector. This estimate is not a measured requirement.

## Required reproducible probe

Record exact values here after running:

```powershell
# Record this exact output first.
docker image inspect vllm/vllm-openai-rocm:latest

# Illustrative launch; validate the GPU flags against the existing local setup.
docker run --rm --device=/dev/kfd --device=/dev/dri `
  --group-add video --ipc=host -p 8000:8000 `
  -v "${HOME}/.cache/huggingface:/root/.cache/huggingface" `
  vllm/vllm-openai-rocm:latest `
  --model google/gemma-4-E2B-it `
  --max-model-len 8192 --limit-mm-per-prompt '{"image":1}'

$Env:VLLM_MODEL = 'google/gemma-4-E2B-it'
& .venv/bin/python scripts/test_vllm_image.py path/to/approved-test-image.jpg
```

| Result | Value |
|---|---|
| vLLM version/image digest | not run |
| ROCm visible inside container | not run |
| Model revision/hash | not run |
| Image request accepted | not run |
| Cold load memory | not run |
| Peak single-request memory | not run |
| Median/p95 latency across 10 requests | not run |
| Detector-only FPS | not run |
| Combined detector FPS | not run |
| Two-hour stability | not run |

## Decision

Gemma 4 is verified to exist and to support image input through current vLLM. Gemma 4 on this particular Strix Halo/Fedora container stack is **not yet verified**. Until every probe above passes without destabilising detection, use mock/replay for descriptions and detector-only for a live feed. Never fail over automatically to an external provider.
