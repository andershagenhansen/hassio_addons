## 1.0.23
- Fix: add python-multipart to Dockerfile — required by FastAPI for file upload (UploadFile); server crashed on startup without it

## 1.0.22
- Add ffmpeg to Dockerfile — ensures torchaudio can decode MP3 and other formats for voice cloning

## 1.0.21
- Fix: voice clone upload now decodes any audio format (MP3, OGG, FLAC, …) via torchaudio before extracting the speaker embedding — previously the raw bytes were saved with a .wav extension and passed directly, causing silent failures or crashes on non-WAV uploads

## 1.0.20
- Add voice cloning ("Stemmekloning") tab in the web UI — upload a WAV/MP3 clip to clone a speaker via Kanade's global embedding; cloned speakers are persisted in /data/cloned_speakers/ and survive restarts; delete cloned speakers from the UI; cloned voices appear immediately in the main speaker row

## 1.0.19
- Fix: UI API calls now work through HAOS ingress — derive BASE from window.location.pathname so fetch paths include the ingress prefix (e.g. /abc123_plapre_tts_server/v1/audio/speech) instead of hitting the HA root

## 1.0.18
- Fix: synthesis now works — with the transformers 5.x TokenizersBackend tokenizer, convert_tokens_to_ids() returns None for pico's added special tokens; patch inference.py to resolve all token IDs via get_vocab() and guard against None in generate(eos_token_id=…); verified with Docker: 135/135 phrases generated, zero failures
- Fix: pre-install transformers>=5.0.0 in Dockerfile to ensure correct version is present at first-boot plapre install time

## 1.0.17
- (superseded) attempted transformers~=4.48.0 pin — reverted; model tokenizer requires transformers 5.x
- Fix: log full tracebacks from pre-gen failures (exc_info=True) so synthesis errors are visible

## 1.0.16
- Speaker is now a dropdown select in HA (tor|ida|liv|ask|kaj) instead of a free-text field
- Pre-generation now runs for all 5 voices at startup (135 phrases total)

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
