import whisper
import torch
from pyannote.audio import Pipeline
import sys

def transcribe_and_diarize(audio_file, hf_token):
    # Step 1: Transcribe with Whisper
    print("Transcribing with Whisper...")
    model = whisper.load_model("large-v3")
    result = model.transcribe(audio_file, language="es")
    
    # Step 2: Diarize with modern PyAnnote
    print("Diarizing with PyAnnote...")
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=hf_token
    )
    
    diarization = pipeline(audio_file)
    
    # Combine results (basic version)
    print("\nTranscription:")
    print(result["text"])
    
    print("\nSpeaker segments:")
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        print(f"Speaker {speaker}: {turn.start:.1f}s - {turn.end:.1f}s")

if __name__ == "__main__":
    transcribe_and_diarize("output.mp3", sys.argv[1])
