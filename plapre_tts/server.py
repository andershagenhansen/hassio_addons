import hashlib, io, json, logging, os, struct, subprocess, sys, tempfile, threading
from pathlib import Path
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
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
SPEAKERS = ["tor", "ida", "liv", "ask", "kaj"]
CACHE_DIR = Path("/data/phrases")

# Load pre-defined phrases
_PHRASE_FILE = Path(__file__).parent / "phrases.json"
DEFAULT_PHRASES: list[str] = json.loads(_PHRASE_FILE.read_text()) if _PHRASE_FILE.exists() else []

app = FastAPI(title="Plapre TTS", version="1.0.8")
tts = None  # initialised on first boot after plapre install
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
    if tts is None:
        raise RuntimeError("Model not ready yet — still initialising")
    audio = tts.speak(text, speaker=speaker)
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
    speakers = [SPEAKER]  # pre-generate for the default speaker
    total = len(DEFAULT_PHRASES) * len(speakers)
    done = 0
    for spk in speakers:
        for phrase in DEFAULT_PHRASES:
            if not _get_cached(phrase, spk):
                log.info(f"[pre-gen {done+1}/{total}] [{spk}] {phrase}")
                try:
                    _synthesize(phrase, spk)
                except Exception as exc:
                    log.warning(f"Pre-gen failed for {phrase!r}: {exc}")
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
        subprocess.run([sys.executable, "-m", "pip", "install", "--no-cache-dir",
                        "--no-build-isolation", src], check=True)
    log.info("plapre installed successfully")


@app.on_event("startup")
async def startup():
    global tts
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _install_plapre()
    from plapre import Plapre
    log.info(f"Loading model: {MODEL}")
    tts = Plapre(MODEL)
    log.info("Model ready")
    threading.Thread(target=_pregenerate_phrases, daemon=True, name="pre-gen").start()


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

class SpeechRequest(BaseModel):
    input: str
    voice: str = "ida"


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
