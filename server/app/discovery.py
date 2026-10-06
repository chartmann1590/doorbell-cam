"""Camera discovery: mDNS browse -> subnet HTTP probe -> manual fallback.

The ESP32-CAM advertises mDNS hostname `doorbellcam.local` with service
`_doorbellcam._tcp`. The hub resolves it, or finds it by probing every host on
the local /24 for the /api/whoami marker. CAM_IP from .env is the final
fallback so the system can always be connected manually.
"""
import ipaddress
import logging
import socket
import time
from typing import Optional

import requests
from zeroconf import IPVersion, ServiceBrowser, Zeroconf

from .config import settings

log = logging.getLogger("doorbell.discovery")

WHOAMI_MARKER = '"product": "doorbellcam"'  # matched loosely below
PROBE_TIMEOUT = 0.35


class _Listener:
    def __init__(self):
        self.found_ip: Optional[str] = None
        self.name: Optional[str] = None

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        try:
            info = zc.get_service_info(type_, name, 3000)
            if info and info.addresses:
                ip = socket.inet_ntoa(info.addresses[0])
                self.found_ip = ip
                self.name = name.split(".")[0]
                log.info("mDNS found camera %s at %s", self.name, ip)
        except Exception as e:  # noqa: BLE001
            log.debug("mDNS add_service error: %s", e)

    def update_service(self, zc, type_, name) -> None:  # noqa: ANN001
        pass


def _whoami_ok(ip: str, port: int = 80) -> bool:
    try:
        r = requests.get(f"http://{ip}:{port}/api/whoami", timeout=PROBE_TIMEOUT)
        if r.status_code == 200:
            text = r.text.replace(" ", "")
            return '"product":"doorbellcam"' in text
    except Exception:  # noqa: BLE001
        pass
    return False


def _local_subnet() -> str:
    if settings.LOCAL_SUBNET:
        return settings.LOCAL_SUBNET
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return str(ipaddress.ip_network(f"{ip}/24", strict=False).network_address)


def _probe_subnet() -> Optional[str]:
    net = ipaddress.ip_network(f"{_local_subnet()}/24", strict=False)
    hosts = [str(h) for h in net.hosts()]
    log.info("Probing %d hosts for camera marker…", len(hosts))

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=64) as ex:
        for ip in ex.map(_whoami_ok, hosts):
            if ip:
                return ip
    return None


def discover_camera(allow_subnet_scan: bool = True) -> Optional[str]:
    """Return camera base IP, trying mDNS, then subnet scan, then .env."""
    # 1) mDNS
    try:
        zc = Zeroconf()
        listener = _Listener()
        ServiceBrowser(zc, "_doorbellcam._tcp.local.", listener)
        deadline = time.time() + 6
        while time.time() < deadline and listener.found_ip is None:
            time.sleep(0.2)
        zc.close()
        if listener.found_ip and _whoami_ok(listener.found_ip):
            return listener.found_ip
    except Exception as e:  # noqa: BLE001
        log.warning("mDNS browse failed: %s", e)

    # 2) hostname resolution fallback
    for host in ("doorbellcam.local",):
        try:
            ip = socket.gethostbyname(host)
            if _whoami_ok(ip):
                log.info("Resolved %s -> %s", host, ip)
                return ip
        except Exception:  # noqa: BLE001
            pass

    # 3) subnet scan
    if allow_subnet_scan:
        try:
            ip = _probe_subnet()
            if ip:
                log.info("Subnet scan found camera at %s", ip)
                return ip
        except Exception as e:  # noqa: BLE001
            log.warning("Subnet scan failed: %s", e)

    # 4) manual fallback from .env
    if settings.CAM_IP:
        if _whoami_ok(settings.CAM_IP):
            log.info("Using CAM_IP fallback %s", settings.CAM_IP)
            return settings.CAM_IP

    return None
