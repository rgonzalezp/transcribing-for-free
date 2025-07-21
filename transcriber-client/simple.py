# simple_upload.py
import requests
import sys
from pathlib import Path

SERVER = "http://192.168.1.159:8000"   # <- replace with your server's IP:port
FILE   = Path(sys.argv[1])
LANG   = "es"                          # or "en"

with FILE.open("rb") as fh:
    resp = requests.post(
        f"{SERVER}/transcribe",
        files={"audio": ("audio", fh)},
        data={"lang": LANG},
        timeout=None,                  # allow long jobs
        stream=True,                   # let us stream the response
    )

print("Status:", resp.status_code)
print("First 400 bytes of response ↓\n")
for chunk in resp.iter_content(400):
    print(chunk.decode(errors="ignore"))
    break
