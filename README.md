FRIXO PROXY TOOL — Proxy Scraper \& Checker v1.0

Official automation software developed for FRIXO Tool Hub clients. This utility validates and tests proxy connections using asynchronous concurrency, automated HTTP proxy scraping, and latency tracking routines.



1\. System Requirements

Operating System: Windows 10 / Windows 11



Runtime: Python 3.10+ (Ensure "Add Python to PATH" is checked during installation)



Network: Active internet connection (No paid proxies required)



2\. File Architecture

FRIXO-Proxy-Tool/

├── proxy.py         (Asynchronous core engine \& proxy scraper)

├── run.bat          (1-Click execution script)

├── requirements.txt (Python dependency declarations)

├── your\_proxy.txt   (Optional custom proxy input file)

├── working\_proxies.txt (Output file for live proxies)

└── README.md        (Technical user manual)



3\. Quick Start Guide

Step 1: Unpack Package

Extract the entire FRIXO-Proxy-Tool zip archive to a location on your local system (such as Desktop or Documents).



Step 2: Launch the Suite

Double-click run.bat.

Note: On the initial launch, the script automatically verifies environment dependencies and installs missing libraries (requests, colorama).



Step 3: Enter Parameters

When prompted by the FRIXO interface:

\- Run in normal scraper mode automatically or pass custom files via arguments.



4\. Configuration Parameters (Command Line Arguments)

Customize execution settings directly via terminal flags:



\--input (-i): Path to a custom proxy text file (IP:PORT format). Default: None (Auto-scrapes).



\--threads (-t): Number of concurrent threads for checking proxies. Default: 50.



\--timeout: Proxy connection timeout in seconds. Default: 5.



\--output (-o): Output file for live working proxies. Default: working\_proxies.txt.



5\. Operational Safeguards

Auto Proxy Scraping: Fetches fresh HTTP proxies dynamically on every run to test public endpoints.



Latency Tracking: Measures live response time down to the millisecond for each validated proxy connection.



Multi-Threaded Validation: Uses thread-safe workers to rapidly scan and verify proxy status before exporting results.



6\. Discord Bot 版 (discord\_bot.py + proxy\_engine.py)

`/proxy` コマンド1つで、公開ソースからの収集〜添付リストの検証まで行える高性能版です。

asyncio + aiohttp による完全非同期エンジンで、スレッド方式より大幅に高い同時実行数を1プロセスで捌けます。



Step 1: Discord Developer Portal でBotを作成

- https://discord.com/developers/applications にアクセスし、"New Application" を作成

- 左メニュー "Bot" タブで "Add Bot" → トークンを "Reset Token" で発行してコピー

- "OAuth2" → "URL Generator" で scopes に `bot` と `applications.commands` をチェックし、生成されたURLでサーバーに招待



Step 2: 環境変数を設定

- `.env.example` を `.env` にコピーし、`DISCORD\_BOT\_TOKEN` に発行したトークンを貼り付け

- 必要なら `DEFAULT\_CONCURRENCY` / `DEFAULT\_TIMEOUT` / `CHECK\_URL` を調整



Step 3: 起動

- `run\_bot.bat` をダブルクリック (初回は依存関係を自動インストール)

- 起動ログに `Logged in as ...` が表示されればOK

- `SOCKS support: enabled/disabled` は `aiohttp_socks` がインストールされているかどうかを示す。MrtCloud等、一部のBotホスティングは「プロキシライブラリ」扱いで `aiohttp_socks` を許可しないため、その場合は `requirements.txt` から該当行を外せば `disabled` のまま HTTP プロトコルのみで運用できる (Renderなど制限のないホストでは同梱のままでSOCKS4/5も利用可能)



Step 4: `/proxy` コマンド

```

/proxy [protocol] [concurrency] [timeout] [file]

```

- `protocol` — `HTTP` / `SOCKS4` / `SOCKS5` / `ALL(自動判定)`。未指定時は HTTP。`aiohttp_socks` 未導入のホストでは SOCKS4/SOCKS5/ALL を選ぶと案内メッセージが返り、HTTPのみ利用可能

- `concurrency` — 同時チェック数 (10〜1000、既定 200)。高いほど速いが回線・CPU負荷は増える

- `timeout` — 1プロキシあたりのタイムアウト秒数 (1〜15、既定 6)

- `file` — IP:PORT形式のカスタムリストを添付すると、収集をスキップしてそのリストのみ検証



強化ポイント:

- 複数の公開プロキシフィード (TheSpeedX/PROXY-List, monosans/proxy-list, ProxyScrape API, free-proxy-list.net 等) を同時に収集し重複排除

- スレッドではなく asyncio + aiohttp による非同期I/Oで数百〜千並列のチェックが可能 (任意で `aiohttp\_socks` を追加導入すればSOCKS4/5にも対応。未導入でもHTTPプロキシの収集・検証は完全に動作)

- 生存確認だけでなく **匿名度判定** (elite / anonymous / transparent) を自動付与

- レイテンシ順にソートし、Embedには最速Top15、全件はtxt添付ファイルで受け取れる

- 検証中は進捗をメッセージ編集でリアルタイム表示



7\. Render へのデプロイ (無料 Web Service + keep-alive 方式)

Renderの無料枠は "Web Service" のみで、常駐の "Background Worker" は有料 (月$7〜)。

そこでBot内にヘルスチェック用の簡易HTTPサーバー (`/`, `/health`) を同梱し、Web Serviceとしてデプロイした上で外部サービスから定期pingすることでスリープを回避する構成にしてある。



Step 1: GitHubへプッシュ

- このフォルダの中身をGitHubリポジトリ (public/privateどちらでも可) にプッシュする

- `.env` はコミットしないこと (`.gitignore` 済み)。トークンはRenderのダッシュボードで設定する



Step 2: Renderでサービス作成

- https://dashboard.render.com/ → "New +" → "Blueprint" を選び、このリポジトリを接続すると `render.yaml` の内容で自動セットアップされる

- もしくは "New +" → "Web Service" を選び、手動で以下を設定:

  - Build Command: `pip install -r requirements.txt`

  - Start Command: `python discord_bot.py`

  - Plan: Free



Step 3: 環境変数を設定

- Renderダッシュボードの "Environment" タブで `DISCORD\_BOT\_TOKEN` を設定 (`render.yaml` では `sync: false` にしているため必ず手動入力が必要)

- 必要なら `DEFAULT\_CONCURRENCY` / `DEFAULT\_TIMEOUT` / `CHECK\_URL` も調整

- `PORT` はRenderが自動的に注入するため設定不要 (コード側は `os.environ["PORT"]` を自動で読む)



Step 4: デプロイ確認

- デプロイ完了後、割り当てられたURL (例: `https://frixo-proxy-bot.onrender.com`) にアクセスして `FRIXO Proxy Bot is alive.` と表示されればOK

- Renderのログに `Logged in as ...` が出ていればDiscord側も接続済み



Step 5: スリープ回避 (keep-alive)

- Render無料Web Serviceは15分間HTTPアクセスが無いとスリープする

- https://uptimerobot.com/ 等の無料監視サービスに登録し、5〜10分間隔で Step4 のURL (`/health`) にHTTPリクエストを送るモニターを作成する

- 無料枠は月750インスタンス時間 (常時稼働1サービス分とほぼ同等) のため、pingで起こしっぱなしにしても通常は枠内に収まる



8\. Client Support

For technical support, feature requests, or custom tool development, contact staff via the  Tool Hub Discord server (discord.gg/tool-hub).

