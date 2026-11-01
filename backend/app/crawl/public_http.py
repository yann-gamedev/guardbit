"""Public HTTP transport: validate every destination, pin DNS, never follow redirects."""

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

import httpx

from app.config import settings
from app.crawl.fetcher import _host


class UnsafeTarget(ValueError):
    pass


async def public_address(url: str) -> str:
    host = _host(url)
    if host == "localhost" or host.endswith(".localhost") or "%" in host:
        raise UnsafeTarget("Alamat lokal tidak dapat diperiksa")
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
        addresses = [ipaddress.ip_address(info[4][0]) for info in infos]
    if not addresses:
        raise OSError("Nama domain tidak dapat ditemukan")
    for address in addresses:
        if settings.DEBUG and host == "127.0.0.1" and str(address) == host:
            continue
        if not address.is_global or address.is_multicast:
            raise UnsafeTarget("Alamat jaringan privat tidak dapat diperiksa")
    return str(addresses[0])


async def get_public(url: str, headers: dict) -> httpx.Response:
    address = await public_address(url)
    parsed = urlsplit(url)
    host = _host(url)
    authority = f"[{host}]" if ":" in host else host
    if parsed.port:
        authority += f":{parsed.port}"
    pinned = httpx.URL(url).copy_with(host=address)
    headers = {key: value for key, value in headers.items() if key.lower() not in {"host", "cookie", "authorization"}}
    headers["Host"] = authority
    # Use original hostname for TLS certificate verification, pinned address for TCP.
    async with httpx.AsyncClient(trust_env=False, timeout=30, follow_redirects=False) as client:
        return await client.get(pinned, headers=headers, extensions={"sni_hostname": host})
