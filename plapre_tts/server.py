import hashlib, io, json, logging, os, re, struct, subprocess, sys, tempfile, threading
from pathlib import Path
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("plapre")

# HAOS passes add-on options as /data/options.json
_opts: dict = {}
if os.path.exists("/data/options.json"):
    with open("/data/options.json") as f:
        _opts = json.load(f)

MODEL   = _opts.get("model",   os.getenv("PLAPRE_MODEL",   "syvai/plapre-pico"))
SPEAKER = _opts.get("speaker", os.getenv("PLAPRE_SPEAKER", "ida"))
HF_TOKEN = _opts.get("hf_token", os.getenv("HF_TOKEN", ""))
if HF_TOKEN:
    os.environ["HF_TOKEN"] = HF_TOKEN
SPEAKERS = ["tor", "ida", "liv", "ask", "kaj"]  # updated after startup
CACHE_DIR = Path("/data/phrases")
CLONED_DIR = Path("/data/cloned_speakers")

# Load pre-defined phrases
_PHRASE_FILE = Path(__file__).parent / "phrases.json"
DEFAULT_PHRASES: list[str] = json.loads(_PHRASE_FILE.read_text()) if _PHRASE_FILE.exists() else []

app = FastAPI(title="Plapre TTS", version="1.0.22")
tts = None          # initialised on first boot after plapre install
speaker_embs = {}   # name → torch.Tensor, loaded at startup
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------

def _to_wav(samples: np.ndarray, sr: int = 24000) -> bytes:
    pcm = (np.clip(np.asarray(samples, np.float32), -1.0, 1.0) * 32767).astype(np.int16).tobytes()
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + len(pcm)))
    buf.write(b"WAVEfmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sr, sr * 2, 2, 16))
    buf.write(b"data")
    buf.write(struct.pack("<I", len(pcm)))
    buf.write(pcm)
    return buf.getvalue()


def _cache_key(text: str, speaker: str) -> str:
    return hashlib.md5(f"{speaker}:{text.strip().lower()}".encode()).hexdigest()


def _cache_path(text: str, speaker: str) -> Path:
    return CACHE_DIR / speaker / (_cache_key(text, speaker) + ".wav")


def _get_cached(text: str, speaker: str) -> bytes | None:
    p = _cache_path(text, speaker)
    return p.read_bytes() if p.exists() else None


def _synthesize(text: str, speaker: str) -> bytes:
    import torch
    if tts is None:
        raise RuntimeError("Model not ready yet — still initialising")
    emb = speaker_embs.get(speaker)
    audio = tts.speak(text, speaker_emb=emb)
    if isinstance(audio, tuple):
        audio = audio[0]
    wav = _to_wav(audio)
    # Always cache the result
    p = _cache_path(text, speaker)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(wav)
    return wav


# ---------------------------------------------------------------------------
# Pre-generation at startup (background thread — doesn't block the server)
# ---------------------------------------------------------------------------

def _pregenerate_phrases():
    speakers = SPEAKERS  # pre-generate for all voices
    total = len(DEFAULT_PHRASES) * len(speakers)
    done = 0
    for spk in speakers:
        for phrase in DEFAULT_PHRASES:
            if not _get_cached(phrase, spk):
                log.info(f"[pre-gen {done+1}/{total}] [{spk}] {phrase}")
                try:
                    _synthesize(phrase, spk)
                except Exception as exc:
                    log.warning(f"Pre-gen failed for {phrase!r}: {exc}", exc_info=True)
            done += 1
    log.info(f"Pre-generation complete — {total} phrases cached in {CACHE_DIR}")


def _install_plapre():
    try:
        import plapre  # noqa
        return
    except ImportError:
        pass
    log.info("First boot: installing plapre (this takes ~30s)…")
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "plapre")
        subprocess.run(["git", "clone", "https://github.com/syv-ai/plapre.git", src], check=True)
        subprocess.run(["git", "-C", src, "checkout", "bc8ad9ef61"], check=True)
        with open(os.path.join(src, "pyproject.toml"), "a") as f:
            f.write("\n[tool.hatch.metadata]\nallow-direct-references = true\n")
        # Patch inference.py: with the transformers 5.x TokenizersBackend tokenizer,
        # convert_tokens_to_ids() returns None for the model's added special tokens
        # (<text>, </audio>, <audio_0>, <phone_*>, …). get_vocab() resolves them
        # reliably. Passing None into generate(eos_token_id=…) or torch.tensor()
        # otherwise crashes with "NoneType cannot be interpreted as an integer".
        inf = os.path.join(src, "plapre", "inference.py")
        with open(inf) as f:
            code = f.read()

        patches = [
            (
                '        self.audio_token_start = self.tokenizer.convert_tokens_to_ids("<audio_0>")\n'
                '        self.audio_token_end = self.tokenizer.convert_tokens_to_ids("<audio_12799>")\n'
                '        self.audio_end_id = self.tokenizer.convert_tokens_to_ids("</audio>")\n'
                '        self.eos_id = self.tokenizer.eos_token_id',
                '        self._vocab = self.tokenizer.get_vocab()\n'
                '        self.audio_token_start = self._vocab.get("<audio_0>")\n'
                '        self.audio_token_end = self._vocab.get("<audio_12799>")\n'
                '        self.audio_end_id = self._vocab.get("</audio>")\n'
                '        self.eos_id = self.tokenizer.eos_token_id',
            ),
            (
                '        for c in phonemes:\n'
                '            tid = tok.convert_tokens_to_ids(f"<phone_{c}>")\n'
                '            if tid != tok.unk_token_id:\n'
                '                phone_ids.append(tid)',
                '        for c in phonemes:\n'
                '            tid = self._vocab.get(f"<phone_{c}>")\n'
                '            if tid is not None:\n'
                '                phone_ids.append(tid)',
            ),
            (
                '        text_start = tok.convert_tokens_to_ids("<text>")\n'
                '        text_end = tok.convert_tokens_to_ids("</text>")\n'
                '        ph_start = tok.convert_tokens_to_ids("<phonemes>")\n'
                '        ph_end = tok.convert_tokens_to_ids("</phonemes>")\n'
                '        audio_start = tok.convert_tokens_to_ids("<audio>")',
                '        text_start = self._vocab.get("<text>")\n'
                '        text_end = self._vocab.get("</text>")\n'
                '        ph_start = self._vocab.get("<phonemes>")\n'
                '        ph_end = self._vocab.get("</phonemes>")\n'
                '        audio_start = self._vocab.get("<audio>")',
            ),
            (
                "        return (\n"
                "            [text_start] + text_ids + [text_end]\n"
                "            + [ph_start] + phone_ids + [ph_end, audio_start]\n"
                "        )",
                "        return [\n"
                "            x for x in\n"
                "            [text_start] + text_ids + [text_end]\n"
                "            + [ph_start] + phone_ids + [ph_end, audio_start]\n"
                "            if x is not None\n"
                "        ]",
            ),
            (
                "                eos_token_id=[self.audio_end_id, self.eos_id],",
                "                eos_token_id=[i for i in [self.audio_end_id, self.eos_id] if i is not None],",
            ),
        ]
        for old, new in patches:
            if old not in code:
                raise RuntimeError(f"plapre patch anchor not found:\n{old[:80]}…")
            code = code.replace(old, new)

        with open(inf, "w") as f:
            f.write(code)
        subprocess.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", src],
                       check=True)
    log.info("plapre installed successfully")


def _load_speaker_embs():
    import torch
    from huggingface_hub import hf_hub_download
    log.info("Loading speaker embeddings…")
    path = hf_hub_download(MODEL, "speakers.json")
    raw = json.loads(Path(path).read_text())
    return {name: torch.tensor(vec, dtype=torch.float32) for name, vec in raw.items()}


@app.on_event("startup")
async def startup():
    global tts, speaker_embs
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CLONED_DIR.mkdir(parents=True, exist_ok=True)
    _install_plapre()
    import torch
    from plapre import Plapre
    log.info(f"Loading model: {MODEL}")
    tts = Plapre(MODEL)
    speaker_embs = _load_speaker_embs()
    SPEAKERS.clear()
    SPEAKERS.extend(speaker_embs.keys())
    # Load persisted cloned speakers from /data/cloned_speakers/
    for p in sorted(CLONED_DIR.glob("*.json")):
        emb = torch.tensor(json.loads(p.read_text()), dtype=torch.float32)
        speaker_embs[p.stem] = emb
        if p.stem not in SPEAKERS:
            SPEAKERS.append(p.stem)
    log.info(f"Speakers loaded: {SPEAKERS}")
    log.info("Model ready")
    threading.Thread(target=_pregenerate_phrases, daemon=True, name="pre-gen").start()


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

class SpeechRequest(BaseModel):
    input: str
    voice: str = "ida"


@app.get("/")
def root():
    return FileResponse(Path(__file__).parent / "ui.html", media_type="text/html")


@app.get("/health")
def health():
    cached = sum(1 for _ in CACHE_DIR.rglob("*.wav"))
    return {"status": "ok", "model": MODEL, "default_speaker": SPEAKER, "cached_phrases": cached}


@app.get("/v1/speakers")
def speakers():
    return {"speakers": SPEAKERS, "default": SPEAKER}


@app.get("/v1/phrases")
def list_phrases():
    return {"phrases": DEFAULT_PHRASES, "count": len(DEFAULT_PHRASES)}


@app.post("/v1/clone")
async def clone_speaker(name: str, file: UploadFile = File(...)):
    if tts is None:
        raise HTTPException(503, "Model not ready yet")
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", name.strip())[:32]
    if not name:
        raise HTTPException(400, "name is empty")
    content = await file.read()
    # Write with original extension so torchaudio picks the right decoder
    orig_ext = Path(file.filename).suffix.lower() if file.filename else ".wav"
    with tempfile.NamedTemporaryFile(suffix=orig_ext, delete=False) as tmp:
        tmp.write(content)
        raw_path = tmp.name
    tmp_path = raw_path
    try:
        import torch, torchaudio
        # Decode whatever format was uploaded and resave as 24kHz mono WAV
        waveform, sr = torchaudio.load(raw_path)
        if waveform.shape[0] > 1:
            waveform = waveform.mean(0, keepdim=True)
        if sr != 24000:
            waveform = torchaudio.functional.resample(waveform, sr, 24000)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_tmp:
            tmp_path = wav_tmp.name
        torchaudio.save(tmp_path, waveform, 24000)
        emb = tts._extract_speaker_emb(tmp_path)
        CLONED_DIR.mkdir(parents=True, exist_ok=True)
        (CLONED_DIR / f"{name}.json").write_text(json.dumps(emb.tolist()))
        speaker_embs[name] = emb
        if name not in SPEAKERS:
            SPEAKERS.append(name)
        log.info(f"Cloned speaker {name!r}, norm={float(emb.norm()):.3f}")
        return {"name": name, "norm": float(emb.norm())}
    except Exception as exc:
        log.exception("voice cloning failed")
        raise HTTPException(500, str(exc))
    finally:
        for p in {raw_path, tmp_path}:
            try: os.unlink(p)
            except OSError: pass


@app.get("/v1/cloned-speakers")
def list_cloned():
    cloned = [p.stem for p in sorted(CLONED_DIR.glob("*.json"))] if CLONED_DIR.exists() else []
    return {"cloned": cloned}


@app.delete("/v1/clone/{name}")
def delete_clone(name: str):
    p = CLONED_DIR / f"{name}.json"
    if p.exists():
        p.unlink()
    speaker_embs.pop(name, None)
    if name in SPEAKERS:
        SPEAKERS.remove(name)
    return {"deleted": name}


@app.post("/v1/audio/speech")
def speech(req: SpeechRequest):
    text = req.input.strip()
    if not text:
        raise HTTPException(400, "input is empty")
    spk = req.voice if req.voice in SPEAKERS else SPEAKER

    cached = _get_cached(text, spk)
    if cached:
        log.info(f"[CACHE HIT] [{spk}] {text[:60]}")
        return Response(content=cached, media_type="audio/wav",
                        headers={"X-Cache": "HIT", "X-Speaker": spk})

    log.info(f"[SYNTHESISE] [{spk}] {text[:60]}")
    try:
        wav = _synthesize(text, spk)
    except Exception as exc:
        log.exception("synthesis failed")
        raise HTTPException(500, str(exc))
    return Response(content=wav, media_type="audio/wav",
                    headers={"X-Cache": "MISS", "X-Speaker": spk})
