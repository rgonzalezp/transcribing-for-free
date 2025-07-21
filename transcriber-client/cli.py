#!/usr/bin/env python3
"""
cli.py – LAN WhisperX client.
See README for usage.
"""

import socket, time
from pathlib import Path
from typing import Dict, Tuple

import requests, typer
from tqdm import tqdm
from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf

app = typer.Typer()
seen: Dict[str, Tuple[str, int, str]] = {}          # host → (ip, port, langs)


# ---------------- Zeroconf helpers ----------------
def _on_service(*, zeroconf, service_type, name, state_change, **kw):
    if state_change is not ServiceStateChange.Added:
        return
    info = zeroconf.get_service_info(service_type, name, timeout=2000)
    if not info or not info.addresses:
        return
    ip = socket.inet_ntoa(info.addresses[0])
    langs = info.properties.get(b"langs", b"").decode() or "unknown"
    instance = name.removesuffix("._whisperx._tcp.local.")
    seen[instance] = (ip, info.port, langs)


def _discover(timeout: float = 2.0):
    seen.clear()
    zc = Zeroconf()
    ServiceBrowser(zc, "_whisperx._tcp.local.", handlers=[_on_service])
    time.sleep(timeout)
    zc.close()


# ---------------- CLI commands ----------------
@app.command()
def list(timeout: float = typer.Option(2, help="Seconds to browse LAN")):
    _discover(timeout)
    if not seen:
        typer.echo("No servers discovered."); raise typer.Exit(1)
    typer.echo(f"{'HOST':<22} {'IP:PORT':<22} LANGS")
    for host, (ip, port, langs) in seen.items():
        typer.echo(f"{host:<22} {ip}:{port:<22} {langs}")


@app.command()
def run(
    file: Path = typer.Argument(..., exists=True, readable=True, help="Audio/video file"),
    lang: str = typer.Option(..., "--lang", "-l"),
    host: str = typer.Option(..., "--host", "-h", help="Bonjour instance or IP[:PORT]"),
):
    # ---------- resolve host ----------
    if ":" in host and host.replace(".", "").replace(":", "").isdigit():
        ip, *maybe = host.split(":"); port = int(maybe[0]) if maybe else 8000
    else:
        _discover(1)
        if host not in seen:
            typer.echo(f"Host '{host}' not found."); raise typer.Exit(1)
        ip, port, _ = seen[host]

    url = f"http://{ip}:{port}/transcribe"
    typer.echo(f"→ Sending '{file.name}' to {ip}:{port}  (lang={lang})")

    # ---------- upload with progress ----------
    size = file.stat().st_size
    start = time.perf_counter()
    with file.open("rb") as fh_in:
        with tqdm.wrapattr(
            fh_in, "read",
            total=size, unit="B", unit_scale=True,
            desc="Uploading", colour="green"
        ) as wrapped:
            with requests.post(
                url,
                files={"audio": ("audio", wrapped)},
                data={"lang": lang},
                stream=True,
            ) as resp:
                resp.raise_for_status()
                out = file.with_suffix(file.suffix + f".{lang}.txt")
                with out.open("wb") as fh_out:
                    for chunk in resp.iter_content(8192):
                        fh_out.write(chunk)

    typer.echo(f"✓ Transcript saved → {out}  ({time.perf_counter() - start:0.1f}s)")


if __name__ == "__main__":
    app()
