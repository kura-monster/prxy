import asyncio
import io
import os
import time
from collections import Counter
from typing import Optional

import discord
from aiohttp import web
from discord import app_commands
from dotenv import load_dotenv

from proxy_engine import SOCKS_AVAILABLE, SOURCES, check_proxies, scrape_proxies

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DEFAULT_CONCURRENCY = int(os.getenv("DEFAULT_CONCURRENCY", "200"))
DEFAULT_TIMEOUT = float(os.getenv("DEFAULT_TIMEOUT", "6"))
PORT = int(os.getenv("PORT", "8080"))

MAX_PROXIES = 8000       # hard cap per run to keep local resource usage sane
PROGRESS_MIN_INTERVAL = 3.0  # seconds between Discord message edits

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


def _build_pairs(scraped: dict) -> list:
  pairs = list({(proto, proxy) for proto, proxies in scraped.items() for proxy in proxies})
  return pairs[:MAX_PROXIES]


def _result_file(working: list) -> discord.File:
  lines = [f"{r.proxy}\t{r.protocol}\t{r.latency}s\t{r.anonymity}" for r in working]
  content = "\n".join(lines)
  return discord.File(io.BytesIO(content.encode()), filename="working_proxies.txt")


def _build_embed(working: list, total: int, source_note: str, elapsed: float) -> discord.Embed:
  embed = discord.Embed(
      title="✅ プロキシ収集結果",
      description=f"取得元: {source_note}\n{total} 件中 **{len(working)} 件** が生存 ({elapsed}秒)",
      color=discord.Color.green(),
  )
  top = working[:15]
  embed.add_field(
      name=f"最速 Top {len(top)}",
      value="\n".join(f"`{r.proxy}` — {r.protocol.upper()} — {r.latency}s — {r.anonymity}" for r in top) or "なし",
      inline=False,
  )
  counts = Counter(r.anonymity for r in working)
  embed.set_footer(
      text=(
          f"匿名度  elite: {counts.get('elite', 0)}  "
          f"anonymous: {counts.get('anonymous', 0)}  "
          f"transparent: {counts.get('transparent', 0)}"
      )
  )
  return embed


@tree.command(name="proxy", description="公開ソースからプロキシを収集、または添付リストを検証します")
@app_commands.describe(
    protocol="対象プロトコル (未指定なら HTTP)",
    concurrency=f"同時チェック数 (10〜1000 / 既定 {DEFAULT_CONCURRENCY})",
    timeout=f"タイムアウト秒数 (1〜15 / 既定 {DEFAULT_TIMEOUT})",
    file="任意: IP:PORT 形式のカスタムリスト。指定時は収集をスキップして検証のみ行う",
)
@app_commands.choices(protocol=[
    app_commands.Choice(name="HTTP", value="http"),
    app_commands.Choice(name="SOCKS4", value="socks4"),
    app_commands.Choice(name="SOCKS5", value="socks5"),
    app_commands.Choice(name="ALL (自動判定)", value="all"),
])
async def proxy_command(
    interaction: discord.Interaction,
    protocol: Optional[app_commands.Choice[str]] = None,
    concurrency: app_commands.Range[int, 10, 1000] = DEFAULT_CONCURRENCY,
    timeout: app_commands.Range[float, 1.0, 15.0] = DEFAULT_TIMEOUT,
    file: Optional[discord.Attachment] = None,
):
  await interaction.response.defer(thinking=True)
  proto_value = protocol.value if protocol else "http"

  if proto_value in ("socks4", "socks5", "all") and not SOCKS_AVAILABLE:
    await interaction.followup.send(
        "⚠️ SOCKS検証には `aiohttp_socks` が必要です。`pip install aiohttp_socks` を実行してから再試行してください。"
    )
    return

  start_time = time.perf_counter()
  last_edit = {"t": 0.0}

  async def progress(done, total, alive):
    now = time.monotonic()
    if now - last_edit["t"] < PROGRESS_MIN_INTERVAL and done != total:
      return
    last_edit["t"] = now
    try:
      await interaction.edit_original_response(content=f"🔎 検証中... {done}/{total} 完了 ({alive} 件生存)")
    except discord.HTTPException:
      pass

  if file is not None:
    data = await file.read()
    lines = data.decode(errors="ignore").splitlines()
    raw = list({line.strip() for line in lines if line.strip() and ":" in line})[:MAX_PROXIES]
    if not raw:
      await interaction.followup.send("有効な IP:PORT 形式のプロキシが見つかりませんでした。")
      return
    pairs = [(proto_value, p) for p in raw]
    total_count = len(pairs)
    source_note = f"添付ファイル `{file.filename}`"
  else:
    await interaction.edit_original_response(content="📡 公開ソースからプロキシを収集中...")
    scraped = await scrape_proxies(proto_value)
    pairs = _build_pairs(scraped)
    total_count = len(pairs)
    source_count = sum(len(v) for v in SOURCES.values()) if proto_value == "all" else len(SOURCES[proto_value])
    source_note = f"公開ソース ({source_count} フィード, {proto_value.upper()})"
    if not pairs:
      await interaction.followup.send("プロキシの収集に失敗しました。ソースが一時的に利用できない可能性があります。")
      return

  await interaction.edit_original_response(content=f"🔎 {total_count} 件を検証中... (concurrency={concurrency})")
  working = await check_proxies(pairs, timeout, concurrency, progress_cb=progress)
  working.sort(key=lambda r: r.latency)
  elapsed = round(time.perf_counter() - start_time, 1)

  if not working:
    await interaction.edit_original_response(
        content=f"❌ 生存プロキシが見つかりませんでした。({total_count} 件中 0 件 / {elapsed}秒)"
    )
    return

  await interaction.edit_original_response(content="✅ 完了しました。")
  await interaction.followup.send(
      embed=_build_embed(working, total_count, source_note, elapsed),
      file=_result_file(working),
  )


@client.event
async def on_ready():
  await tree.sync()
  print(f"[+] Logged in as {client.user} (id: {client.user.id})")
  print(f"[+] SOCKS support: {'enabled' if SOCKS_AVAILABLE else 'disabled (pip install aiohttp_socks)'}")


async def _health(request):
  return web.Response(text="FRIXO Proxy Bot is alive.")


async def start_health_server():
  """Binds a tiny HTTP server so Render's free Web Service plan accepts this as
  a valid service and an uptime pinger (e.g. UptimeRobot) can keep it awake."""
  app = web.Application()
  app.router.add_get("/", _health)
  app.router.add_get("/health", _health)
  runner = web.AppRunner(app)
  await runner.setup()
  site = web.TCPSite(runner, "0.0.0.0", PORT)
  await site.start()
  print(f"[+] Health-check server listening on 0.0.0.0:{PORT}")


async def main_async():
  await start_health_server()
  await client.start(TOKEN)


def main():
  if not TOKEN:
    raise SystemExit(
        "DISCORD_BOT_TOKEN が設定されていません。.env ファイルを作成して設定してください (.env.example を参照)。"
    )
  asyncio.run(main_async())


if __name__ == "__main__":
  main()
