Windows network tweaks for mDNS

    UDP 5353 inbound/outbound must be allowed.
    Windows usually blocks it. Run once in an Admin PowerShell:

    New-NetFirewallRule -DisplayName "mDNS incoming" -Direction Inbound  -Protocol UDP -LocalPort 5353 -Action Allow
    New-NetFirewallRule -DisplayName "mDNS outgoing" -Direction Outbound -Protocol UDP -LocalPort 5353 -Action Allow

    If your switch/Wi‑Fi AP isolates multicast, you may need to place both machines on the same SSID/VLAN or fall back to the “static host/IP” flag described below.

The Python zeroconf library is pure‑Python, so it works on Windows without Bonjour/iTunes.