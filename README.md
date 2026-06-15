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

If your VPS gets HTTP 403 from Gram Network API (common on cloud IPs like AWS, GCP, Azure), you need a Cloudflare Worker as proxy.

### Option A: Use Existing Worker (Easiest)

If someone already has a Worker, just add the URL to config.json:

```json
"worker_url": "https://gram.kriptobisnis.workers.dev"
```

Skip to step 5 below. No Cloudflare account needed!

### Option B: Deploy Your Own Worker

#### Step 1 — Create Cloudflare Account (Free)

Go to https://dash.cloudflare.com/sign-up and register.

#### Step 2 — Create API Token

1. Go to https://dash.cloudflare.com/profile/api-tokens
2. Click **"Create Token"**
3. Find **"Edit Cloudflare Workers"** template → click **"Use template"**
4. Or create custom:
   - **Permissions:** Account > Workers Scripts > Edit
   - **Account Resources:** Select your account
5. Click **"Continue to summary"** → **"Create Token"**
6. **Copy the token** (starts with `cfat_...`) — you won't see it again!

#### Step 3 — Get Account ID

1. Go to https://dash.cloudflare.com
2. Click on your account (left sidebar)
3. Look at the URL: `dash.cloudflare.com/3b9c8da4fce77f661ab7aaed81a896a5`
4. The long string after `/` is your **Account ID** — copy it

#### Step 4 — Deploy Worker

```bash
python3 deploy_worker.py
```

- Paste your **Account ID**
- Paste your **API Token**
- The script deploys the Worker and auto-updates config.json

If it asks for a subdomain, enter any name (e.g. `yourname`).

#### Step 5 — Verify

After deploy, your Worker URL will be something like:

```
https://gram-network-proxy.yourname.workers.dev
```

The script adds this to config.json automatically. If you used Option A, make sure `worker_url` is filled in config.json.

#### Step 6 — Run Miner

```bash
python3 miner.py
```

Check logs — if you see user data (balance, mining status), the Worker is working!

### How It Works

```
Your VPS ──► Cloudflare Worker ──► Gram Network API
            (bypasses IP block)
```

Without Worker: VPS IP (AWS/GCP) → blocked (HTTP 403)
With Worker: VPS → Cloudflare → Gram API (allowed)

### Troubleshooting Worker

| Problem | Solution |
|---------|----------|
| `Invalid API token` | Create new token at api-tokens page |
| `Account ID wrong` | Check URL: `dash.cloudflare.com/<ID>` |
| `Worker deploy failed` | Check token has "Workers Scripts > Edit" permission |
| `HTTP 403 still` | Make sure `worker_url` is filled in config.json |
| `No subdomain` | Script will ask you to create one |

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
  1   Account 1       @user1           10.80 ⛏️ active    claim          02:15:30
  2   Account 2       @user2            5.40 💰 ready     claim          00:03:42
  3   Account 3       @user3            0.00 💤 inactive  start          00:01:15

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
