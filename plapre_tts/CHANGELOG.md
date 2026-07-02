## 1.0.6
- Fix: install hatchling before plapre so --no-build-isolation works correctly

## 1.0.5
- Fix: install torchaudio from PyTorch CPU wheel index to avoid missing CUDA library crash

## 1.0.4
- Fix: clone plapre at pinned commit and patch pyproject.toml for hatchling compatibility

## 1.0.3
- Fix: pin plapre to initial release commit (bc8ad9ef) — HEAD switched to vLLM/GGUF and broke pico model compatibility

## 1.0.2
- Fix: upgrade base image to python:3.12-slim (plapre requires Python ≥ 3.12)
- Add `hf_token` option for HuggingFace gated model authentication

## 1.0.1
- Fix: add `hf_token` configuration option for accessing gated HuggingFace models

## 1.0.0
- Initial release
- Danish neural TTS using syvai/plapre-pico running fully locally on CPU
- Pre-generates 27 common Danish phrases at startup for instant playback
- Phrase cache: synthesised audio stored in /data/phrases/ — zero CPU on repeat requests
- REST API compatible with OpenAI TTS format (/v1/audio/speech)
- Five voices: Ida, Tor, Liv, Ask, Kaj
