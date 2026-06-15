# Gram Network Auto Miner

Auto-mining bot for **Gram Network** Telegram Mini App.
Supports **multiple accounts**, random delays, live dashboard, and Cloudflare Worker proxy.

## Features

- ⛏ Auto mining & claiming every 4 hours
- 👥 Multi-account support (unlimited accounts)
- ⏱ Random delay 1-5 min per account (looks natural)
- 📊 Live terminal dashboard with countdown timers
- ☁️ Cloudflare Worker proxy (bypass cloud IP blocks)
- 🔒 Per-account proxy support
- 🔄 Auto-restart on crash

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/DevSelf12/gram-auto-miner.git
cd gram-auto-miner
pip3 install telethon requests
```

### 2. Get Telegram API Credentials

For **each account** you want to mine with:

1. Go to https://my.telegram.org/apps
2. Login with that account's phone number
3. Click "Create new application"
4. Fill: App title = `GramMiner`, Platform = `Android`
5. Copy **api_id** and **api_hash**

### 3. Create Config

```bash
cp config.example.json config.json
nano config.json
```

Fill your accounts:

```json
{
  "accounts": [
    {
      "name": "Akun Utama",
      "api_id": 12345678,
      "api_hash": "abcdef1234567890abcdef1234567890",
      "phone": "+628xxxxxxxxxx",
      "password": "",
      "proxy": ""
    },
    {
      "name": "Akun Kedua",
      "api_id": 87654321,
      "api_hash": "fedcba0987654321fedcba0987654321",
      "phone": "+628yyyyyyyyyy",
      "password": "",
      "proxy": ""
    }
  ],
  "bot_username": "gramnetwork_bot",
  "worker_url": "",
  "random_delay_max_minutes": 5
}
```

**Config explained:**

| Field | Description |
|-------|-------------|
| `name` | Label for the account (any name) |
| `api_id` | From my.telegram.org |
| `api_hash` | From my.telegram.org |
| `phone` | Telegram phone number |
| `password` | 2FA password (leave empty if none) |
| `proxy` | HTTP proxy (optional, format: `http://user:***@ip:port`) |
| `bot_username` | Gram Network bot username |
| `worker_url` | Cloudflare Worker URL (optional) |
| `random_delay_max_minutes` | Max random delay per action (default: 5) |

### 4. First Run (Login)

```bash
python3 miner.py
```

Each account will ask for:
1. Phone code (sent to Telegram)
2. 2FA password (if enabled)

Sessions saved to `session_0.session`, `session_1.session`, etc.
Login only needed once per account.

### 5. Run

```bash
python3 miner.py
```

## Cloudflare Worker (Optional)

If your VPS gets HTTP 403 from Gram Network API (common on cloud IPs):

```bash
python3 deploy_worker.py
```

This creates a free Cloudflare Worker that proxies API requests.

**How it works:**

```
Your VPS ──► Cloudflare Worker ──► Gram Network API
            (bypasses IP block)
```

## Proxy (Optional)

Each account can use a different proxy for extra anonymity:

```json
{
  "name": "Account",
  "proxy": "http://user:***@proxy-ip:port"
}
```

Leave empty (`""`) to skip proxy.

**With Worker + Proxy:**

```
Your VPS ──► Proxy ──► Cloudflare Worker ──► Gram Network API
```

## Dashboard

The bot shows a live terminal dashboard:

```
==============================================================
  GRAM NETWORK AUTO MINER - DASHBOARD
==============================================================
  Accounts: 3 | Mining: 2 | Ready: 1
  Total Balance: 16.20 GRM
==============================================================

  #   Name            Username         Balance Status     Next Action   Countdown
  --- --------------- ---------------- ------- ------------ -------------- ------------
  1   Akun Utama      @rizvanbaihaqi    10.80 ⛏️ active    claim          02:15:30
  2   Akun Kedua      @account2          5.40 💰 ready     claim          00:03:42
  3   Akun Ketiga     @account3          0.00 💤 inactive  start          00:01:15

==============================================================
  Next refresh in 60s | Ctrl+C to stop
==============================================================
```

## Architecture

```
┌─────────────────────────────────────────────┐
│              miner.py (main loop)           │
├─────────────┬─────────────┬─────────────────┤
│  Account 1  │  Account 2  │  Account N      │
│  (async)    │  (async)    │  (async)        │
│  random     │  random     │  random         │
│  delay      │  delay      │  delay          │
└──────┬──────┴──────┬──────┴────────┬────────┘
       │             │               │
       ▼             ▼               ▼
┌──────────────────────────────────────────────┐
│         Cloudflare Worker (optional)         │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│            Gram Network API                  │
└──────────────────────────────────────────────┘
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `config.json not found` | `cp config.example.json config.json` |
| `api_id/api_hash wrong` | Check https://my.telegram.org/apps |
| `HTTP 403` | Deploy Cloudflare Worker |
| `Unauthorized` | Run `python3 miner.py` to re-login |
| Dashboard not clearing | Terminal doesn't support `cls`/`clear` |

## License

MIT
