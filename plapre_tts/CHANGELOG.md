## 1.0.15
- Fix: patch plapre's _build_prompt during install — tokenizer lacks </text>, <phonemes>, </phonemes> tokens so convert_tokens_to_ids returns None for them, which breaks torch.tensor(); filter None from prompt_ids before tensor creation

## 1.0.14
- Fix: install espeak-ng — required by plapre for phonemization

## 1.0.13
- Add HAOS ingress panel — Plapre TTS now appears in the HA sidebar with a built-in GUI
- Serve ui.html from / with relative API URLs so it works through the ingress proxy

## 1.0.12
- Fix: speak() takes speaker_emb= (torch.Tensor), not speaker= (string) — load speaker embeddings from speakers.json at startup and pass the right tensor per request

## 1.0.11
- hf_token is now required — HA will not start the add-on until a HuggingFace token is configured

## 1.0.10
- Fix: remove --no-build-isolation from first-boot pip install — kanade-tokenizer uses uv_build as its build backend which is not importable without isolation; pip's default isolated builds handle all backends automatically

## 1.0.9
- Fix: explicitly install numpy — uv was not pulling it as a transitive dep of torch

## 1.0.8
- Fix: copy phrases.json into Docker image so pre-generation actually runs on startup
- Fix: defer plapre install to first boot — Docker build is now ~30s faster

## 1.0.7
- (skipped)

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
