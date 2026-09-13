"""High-throughput async proxy scraping & validation engine.

Uses aiohttp (+ aiohttp_socks for SOCKS4/5) so thousands of proxies can be
checked concurrently via a single event loop, instead of one-thread-per-proxy.
"""

import asyncio
import os
import re
import time
from dataclasses import dataclass
from typing import Callable, Optional

import aiohttp

try:
  from aiohttp_socks import ProxyConnector
  SOCKS_AVAILABLE = True
except ImportError:
  SOCKS_AVAILABLE = False

UA_HEADERS = {"User-Agent": "Mozilla/5.0 (FRIXO-Proxy-Bot)"}
CHECK_URL = os.getenv("CHECK_URL", "http://httpbin.org/get")
IP_ECHO_URL = "https://api.ipify.org"
FETCH_TIMEOUT = 12

PROXY_RE = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{2,5})\b")


def _new_connector(limit: int = 100) -> aiohttp.TCPConnector:
  # Force the plain getaddrinfo-based resolver: aiohttp defaults to aiodns
  # (raw UDP DNS queries) when it's installed, which breaks under sandboxes,
  # some VPNs, and networks that only permit resolution via the OS stub resolver.
  return aiohttp.TCPConnector(limit=limit, resolver=aiohttp.ThreadedResolver())

# Continuously-updated public proxy lists + free-proxy-list.net (HTML table).
SOURCES = {
    "http": [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        "https://www.proxy-list.download/api/v1/get?type=http",
        "https://free-proxy-list.net/",
    ],
    "socks4": [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4&timeout=10000&country=all",
    ],
    "socks5": [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=10000&country=all",
    ],
}


@dataclass
class ProxyResult:
  proxy: str
  protocol: str
  latency: float
  anonymity: str


async def fetch_source(session: aiohttp.ClientSession, url: str) -> set:
  proxies = set()
  try:
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=FETCH_TIMEOUT)) as resp:
      if resp.status == 200:
        text = await resp.text(errors="ignore")
        for ip, port in PROXY_RE.findall(text):
          proxies.add(f"{ip}:{port}")
  except Exception:
    pass
  return proxies


async def scrape_proxies(protocol: str = "http") -> dict:
  """Returns {protocol: set(proxies)} pulled from all sources for the given protocol(s)."""
  protocols = list(SOURCES.keys()) if protocol == "all" else [protocol]
  result = {p: set() for p in protocols}

  async with aiohttp.ClientSession(connector=_new_connector(), headers=UA_HEADERS) as session:
    tasks, owners = [], []
    for p in protocols:
      for url in SOURCES.get(p, []):
        tasks.append(fetch_source(session, url))
        owners.append(p)
    fetched = await asyncio.gather(*tasks)

  for owner, proxies in zip(owners, fetched):
    result[owner].update(proxies)
  return result


async def get_real_ip() -> Optional[str]:
  try:
    async with aiohttp.ClientSession(connector=_new_connector(limit=1), headers=UA_HEADERS) as session:
      async with session.get(IP_ECHO_URL, timeout=aiohttp.ClientTimeout(total=5)) as resp:
        if resp.status == 200:
          return (await resp.text()).strip()
  except Exception:
    pass
  return None


def _classify_anonymity(headers: dict, real_ip: Optional[str]) -> str:
  proxy_marker_keys = {"via", "x-forwarded-for", "forwarded", "x-proxy-id", "x-real-ip"}
  header_keys = {k.lower() for k in headers.keys()}

  if real_ip and any(real_ip in str(v) for v in headers.values()):
    return "transparent"
  if header_keys & proxy_marker_keys:
    return "anonymous"
  return "elite"


async def _check_http(session: aiohttp.ClientSession, proxy: str, timeout: float, real_ip):
  start = time.perf_counter()
  try:
    async with session.get(
        CHECK_URL,
        proxy=f"http://{proxy}",
        timeout=aiohttp.ClientTimeout(total=timeout),
    ) as resp:
      if resp.status != 200:
        return None
      data = await resp.json(content_type=None)
      latency = round(time.perf_counter() - start, 3)
      return ProxyResult(proxy, "http", latency, _classify_anonymity(data.get("headers", {}), real_ip))
  except Exception:
    return None


async def _check_socks(proxy: str, version: int, timeout: float, real_ip):
  if not SOCKS_AVAILABLE:
    return None
  start = time.perf_counter()
  try:
    connector = ProxyConnector.from_url(f"socks{version}://{proxy}", rdns=True)
    async with aiohttp.ClientSession(connector=connector, headers=UA_HEADERS) as session:
      async with session.get(CHECK_URL, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
        if resp.status != 200:
          return None
        data = await resp.json(content_type=None)
        latency = round(time.perf_counter() - start, 3)
        return ProxyResult(proxy, f"socks{version}", latency, _classify_anonymity(data.get("headers", {}), real_ip))
  except Exception:
    return None


async def check_proxies(
    pairs: list,
    timeout: float,
    concurrency: int,
    progress_cb: Optional[Callable] = None,
) -> list:
  """pairs: list of (protocol, proxy) tuples. protocol may be 'all' to auto-detect."""
  real_ip = await get_real_ip()
  semaphore = asyncio.Semaphore(concurrency)
  results = []
  completed = 0
  total = len(pairs)
  lock = asyncio.Lock()

  http_session = aiohttp.ClientSession(connector=_new_connector(limit=0), headers=UA_HEADERS)

  async def _auto(proxy):
    result = await _check_http(http_session, proxy, timeout, real_ip)
    if result:
      return result
    if SOCKS_AVAILABLE:
      result = await _check_socks(proxy, 5, timeout, real_ip)
      if result:
        return result
      result = await _check_socks(proxy, 4, timeout, real_ip)
      if result:
        return result
    return None

  async def _worker(protocol, proxy):
    nonlocal completed
    async with semaphore:
      if protocol == "socks4":
        result = await _check_socks(proxy, 4, timeout, real_ip)
      elif protocol == "socks5":
        result = await _check_socks(proxy, 5, timeout, real_ip)
      elif protocol == "all":
        result = await _auto(proxy)
      else:
        result = await _check_http(http_session, proxy, timeout, real_ip)

    if result:
      results.append(result)

    async with lock:
      completed += 1
      if progress_cb and (completed == total or completed % max(1, total // 10) == 0):
        await progress_cb(completed, total, len(results))

  try:
    await asyncio.gather(*(_worker(protocol, proxy) for protocol, proxy in pairs))
  finally:
    await http_session.close()

  return results
