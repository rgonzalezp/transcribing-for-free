# LAN‑Transcriber

**LAN‑Transcriber** lets any computer on your local network off‑load long audio or video recordings to a more powerful "transcription server" that runs **WhisperX (large‑v3, Spanish & English, with speaker diarization)**.  
Everything stays *inside* your LAN—no cloud services or API fees.

```
Client (cli.py / curl.exe)  ───▶  FastAPI server  ── ffmpeg  ──►  WhisperX
          ◀───────────────────────────────────────────────────────────────
                     transcript.txt streamed back chunk‑by‑chunk
```

---

## 🚀 Quick setup

### 0. Network prerequisites

| Platform | What to enable |
|----------|----------------|
| **All routers/Wi‑Fi APs** | Disable *Client/AP isolation* **or** enable *mDNS/Bonjour repeater* so multicast UDP 5353 passes between Wi‑Fi & Ethernet. |
| **macOS server** | Bonjour is built‑in; nothing to install. |
| **Windows client** | Install **Bonjour Print Services** <https://support.apple.com/kb/DL999> for `dns‑sd.exe` and mDNS. |
| **Windows firewall** | *Allow an app* → enable **Bonjour Service** (mDNSResponder.exe) **and** `python.exe` for *Private* networks. |

### 1. Clone & virtual‑env (server *and* client)

> Commands assume macOS / Linux for the server.  
> Replace `brew` with your package manager on Linux and follow the same `uv` steps on Windows.

```bash
# 1) clone on each machine
git clone https://your‑repo‑url/lan‑transcriber.git
cd lan‑transcriber

# 2) create and activate a virtual‑env
# macOS/Linux
brew install ffmpeg uv               # ffmpeg is required on both sides
uv venv .venv && source .venv/bin/activate

# Windows PowerShell
winget install ffmpeg
python -m venv .venv ; .\.venv\Scripts\Activate
```

### 2. Install Python dependencies (same for server & client)

```bash
uv pip install whisperx[diarization] zeroconf typer[all] requests tqdm                fastapi uvicorn[standard] python-multipart
```

### 3. Server‑only final step

```bash
# Hugging Face token is required for pyannote speaker‑diarization checkpoints
export HF_TOKEN=hf_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
# (PowerShell) setx HF_TOKEN "hf_xxx"

# start the HTTP worker (port 8000)
uvicorn server:app --host 0.0.0.0 --port 8000
```

*(Optional) Run `python register.py &` in another terminal to advertise the
service via Bonjour/mDNS so the CLI can discover it automatically.*

---

## ✅ Progressive smoke tests

| # | What to run | Example command | Expected |
|---|-------------|-----------------|----------|
| 1 | Health ping | `curl http://SERVER:8000/health` | `{"status":"healthy",…}` |
| 2 | Upload‑echo | **Windows PowerShell**:<br>`curl.exe -X POST "http://SERVER:8000/upload" -F "audio=@test.mp4"`  <br>**or**<br>`Invoke-WebRequest -Uri "http://SERVER:8000/upload" -Method Post -Form @{ audio = Get-Item 'test.mp4' }` | `{"filename":"test.mp4","bytes_received":…}` |
| 3 | Tiny WAV transcription | `ffmpeg -f lavfi -i sine=frequency=1000:duration=5 -ac 1 -ar 16000 beep.wav`<br>`curl.exe -X POST "http://SERVER:8000/transcribe" -F "audio=@beep.wav" -F "lang=es"` | Short transcript prints |
| 4 | Full file via curl | `curl.exe -X POST "http://SERVER:8000/transcribe" -F "audio=@test.mp4" -F "lang=es" -o transcript.txt` | `transcript.txt` grows until done |
| 5 | Discover servers | `python cli.py list` | Table with `HOST  IP:PORT  LANGS` |
| 6 | Full CLI run | `python cli.py run test.mp4 --lang es --host RicardoacStudio` | Upload & download progress bars |

If any step fails check the server console for FFmpeg/WhisperX errors and verify
`HF_TOKEN` is exported.

---

## 🔍 In‑depth setup

### 1. HTTP API (server.py)

| Route | What it does |
|-------|--------------|
| **`POST /transcribe`** | *fast path* – converts input to 16 kHz mono WAV using **FFmpeg**, then spawns WhisperX:<br>`whisperx WAV --model large-v3 --language <es|en> --diarize --diarize_model pyannote/speaker-diarization-3.1 --output_format txt --device cpu --compute_type float32`<br>The resulting `transcription.txt` is streamed back to the client. |
| **`POST /upload`** | Debug endpoint; counts bytes received and echoes JSON. |
| **`GET /health`** | Returns JSON status plus which device & compute type WhisperX will use. |

*The server chooses `cpu` & `float32` by default. If CUDA is available it switches to `cuda` & `float16` automatically. (M‑series Macs deliberately stay on CPU because MPS still has WhisperX issues.)*

### 2. Zeroconf advertising (optional)

Running `register.py` registers  
`<hostname>._whisperx._tcp.local. : 8000 TXT langs=es,en`  
so the CLI can discover servers with `python cli.py list` on any machine
supporting Bonjour/mDNS.

### 3. CLI behaviour

```text
python cli.py list                         # discover servers
python cli.py run FILE --lang es --host HostName
```

* Uses Zeroconf to resolve `HostName`.  
* Streams file upload with a progress bar (`tqdm`), then writes the transcript
  to `FILE.es.txt`.

### 4. Detailed server configuration

* **Device selection** – `server.py` decides at import‑time  
  * `cpu / float32` (default, works on Apple Silicon & Windows)  
  * `cuda / float16` (if NVIDIA CUDA present)
* **Model flag** inside `run_whisperx`  
  * `--model large-v3` (≈ 12 GB RAM, highest accuracy)  
    *Change to* `distil-large-v3` (~5 GB RAM) if memory is tight.
* **Output** – server streams `transcription.txt` (UTF‑8).

### 5. Typical performance (Mac Studio M2 Max)

| Model (CPU) | 3 h recording | Peak RAM |
|-------------|--------------:|---------:|
| **large‑v3 float32** | ~70 min | ~12 GB |
| distil‑large‑v3 float16 | ~45 min | ~5 GB |

*(Change `--model` & `--compute_type` flags in `server.py` if you want smaller models.)*

### 6. Networking tips

* **macOS firewall** – System Settings ▸ Network ▸ Firewall ▸ Options → allow *Python* or *Terminal* incoming.
* **Windows firewall** – Control Panel ▸ Defender Firewall → *Allow an app* → allow **Bonjour Service** and `python.exe` on *Private* network.
* **Router** – Ensure UDP 5353 (mDNS) is not blocked if you use Zeroconf discovery.

---

## 🧩 Command mini‑cheatsheet

| Task | macOS/Linux (bash) | Windows PowerShell |
|------|--------------------|--------------------|
| Convert MP4 → WAV | `ffmpeg -i file.mp4 -ac 1 -ar 16000 file.wav` | same |
| Upload‑echo test | `curl -X POST http://SERVER:8000/upload -F "audio=@file.wav"` | `Invoke-WebRequest -Uri "http://SERVER:8000/upload" -Method Post -Form @{ audio = Get-Item 'file.wav' }` |
| Full transcription | `curl -X POST http://SERVER:8000/transcribe -F "audio=@file.wav" -F "lang=en" -o out.txt` | `curl.exe -X POST "http://SERVER:8000/transcribe" -F "audio=@file.wav" -F "lang=en" -o out.txt` |
| Discover via dns‑sd | `dns-sd -B _whisperx._tcp` | after Bonjour install: `dns-sd -B _whisperx._tcp` |
| CLI discovery | `python cli.py list` | same |
| CLI run | `python cli.py run file.wav --lang en --host Instance` | same |

---

That's all you need: clone → install → start server → curl or CLI.  
If each smoke test passes in order, you'll end with a fully offline, speaker‑aware Spanish/English transcript pipeline running entirely on your LAN.
