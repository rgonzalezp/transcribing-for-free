from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import StreamingResponse
import subprocess, tempfile, os, shutil, asyncio, torch

app = FastAPI()

# ----------------------------------------------------------------------
# Select the best backend at import-time (FIXED for M2 Mac)
# ----------------------------------------------------------------------
BACKEND_DEVICE, COMPUTE_TYPE = "cpu", "float32"  # safe default

# Force CPU on M2 Mac due to WhisperX/faster-whisper MPS issues
if torch.cuda.is_available():
    # Only use CUDA if actually available (not on M2 Mac)
    BACKEND_DEVICE, COMPUTE_TYPE = "cuda", "float16"
# Note: Commented out MPS due to WhisperX compatibility issues
# elif torch.backends.mps.is_available() and torch.backends.mps.is_built():
#     BACKEND_DEVICE, COMPUTE_TYPE = "mps", "float16"

print(f"WhisperX will run on {BACKEND_DEVICE} with {COMPUTE_TYPE}")

# ----------------------------------------------------------------------
# WhisperX runner (FIXED error handling and cleanup)
# ----------------------------------------------------------------------
async def run_whisperx(wav_path: str, lang: str):
    out_dir = tempfile.mkdtemp()
    
    try:
        cmd = [
            "whisperx", wav_path,
            "--model", "large-v3",
            "--language", lang,
            "--diarize",
            "--diarize_model", "pyannote/speaker-diarization-3.1",
            "--hf_token", os.getenv("HF_TOKEN", ""),
            "--output_dir", out_dir,
            "--device", BACKEND_DEVICE,
            "--compute_type", COMPUTE_TYPE,
            "--output_format", "txt",
        ]
        
        # Set environment variables to avoid device issues
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = "" if BACKEND_DEVICE == "cpu" else env.get("CUDA_VISIBLE_DEVICES", "")
        env["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
        
        proc = await asyncio.create_subprocess_exec(
            *cmd, 
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            error_msg = stderr.decode() if stderr else "WhisperX failed"
            raise RuntimeError(f"WhisperX failed: {error_msg}")
        
        # Check what files were actually created
        all_files = os.listdir(out_dir)
        print(f"Files created by WhisperX: {all_files}")
        
        # Try to find any output file (json, txt, etc.)
        output_files = [f for f in all_files if f.endswith(('.json', '.txt', '.srt', '.vtt'))]
        if not output_files:
            raise RuntimeError(f"WhisperX produced no output files. Files found: {all_files}")
        
        # Use the first output file found
        output_file = os.path.join(out_dir, output_files[0])
        print(f"Using output file: {output_file}")
        
        # Read and stream the file
        with open(output_file, "rb") as f:
            while (chunk := f.read(8192)):
                yield chunk
                
    except Exception as e:
        yield f"Error: {str(e)}".encode()
    finally:
        # Clean up temp files
        try:
            os.unlink(wav_path)
        except:
            pass
        shutil.rmtree(out_dir, ignore_errors=True)

# ----------------------------------------------------------------------
# /transcribe – audio → WAV → WhisperX (FIXED file handling)
# ----------------------------------------------------------------------
@app.post("/transcribe")
async def transcribe(audio: UploadFile, lang: str = Form(...)):
    # Create temporary WAV file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        tmp_wav = tmp_file.name
    
    try:
        # Convert audio to WAV using FFmpeg
        ffmpeg = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", "pipe:0", "-ac", "1", "-ar", "16000",
            tmp_wav, "-y", "-loglevel", "quiet",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Stream audio data to FFmpeg
        while (chunk := await audio.read(8192)):
            ffmpeg.stdin.write(chunk)
        
        ffmpeg.stdin.close()
        returncode = await ffmpeg.wait()
        
        if returncode != 0:
            raise RuntimeError(f"Audio conversion failed with return code: {returncode}")
        
        # Stream the transcription result
        return StreamingResponse(
            run_whisperx(tmp_wav, lang),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="transcript.json"'},
        )
        
    except Exception as e:
        # Clean up on error
        try:
            os.unlink(tmp_wav)
        except:
            pass
        return {"error": str(e)}

# ----------------------------------------------------------------------
# /upload – debugging endpoint (FIXED)
# ----------------------------------------------------------------------
@app.post("/upload")
async def upload_only(audio: UploadFile):
    size = 0
    while (chunk := await audio.read(8192)):
        size += len(chunk)
    return {"filename": audio.filename, "bytes_received": size}

# ----------------------------------------------------------------------
# Health check endpoint
# ----------------------------------------------------------------------
@app.get("/health")
async def health_check():
    return {"status": "healthy", "device": BACKEND_DEVICE, "compute_type": COMPUTE_TYPE}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)