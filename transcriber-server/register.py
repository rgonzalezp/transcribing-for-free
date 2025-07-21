from zeroconf import Zeroconf, ServiceInfo
import socket, sys, os, time

z = Zeroconf()
hostname = socket.gethostname()
ip = socket.gethostbyname(hostname)
info = ServiceInfo(
    type_="_whisperx._tcp.local.",
    name=f"{hostname}._whisperx._tcp.local.",
    port=8000,
    addresses=[socket.inet_aton(ip)],
    properties={"langs": "es,en"}
)
z.register_service(info)
try:
    while True: time.sleep(3600)
except KeyboardInterrupt:
    z.unregister_service(info); z.close()
