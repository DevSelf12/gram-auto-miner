# Gram Network Auto Miner

Auto-mining bot for **Gram Network** Telegram Mini App. Runs 24/7 on VPS, auto-claims every 4 hours.

## Features

- Auto start mining every 4 hours
- Auto claim tokens after each session
- Auto claim daily rewards
- Fresh initData generated via Telethon (no manual refresh)
- Cloudflare Worker proxy (bypass cloud IP restrictions)
- Systemd service for 24/7 operation
- Auto-restart on crash

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/DevSelf12/gram-auto-miner.git
cd gram-auto-miner
pip3 install telethon requests
```

### 2. Get Telegram API Credentials

1. Go to https://my.telegram.org/apps
2. Login with your phone number
3. Click "Create new application"
4. Fill: App title = `GramMiner`, Platform = `Android`
5. Copy **api_id** (number) and **api_hash** (string)

### 3. Create Config

```bash
cp config.example.json config.json
nano config.json
```

Fill your credentials:

```json
{
  "api_id": 12345678,
  "api_hash": "abcdef1234567890abcdef1234567890",
  "phone": "+628xxxxxxxxxx",
  "password": "",
  "bot_username": "gramnetwork_bot",
  "worker_url": ""
}
```

| Field | Description |
|-------|-------------|
| `api_id` | From my.telegram.org |
| `api_hash` | From my.telegram.org |
| `phone` | Your Telegram phone number |
| `password` | 2FA password (leave empty if none) |
| `bot_username` | Gram Network bot username |
| `worker_url` | Cloudflare Worker URL (optional) |

### 4. First Run (Login)

```bash
python3 miner.py
```

First run will ask for:
1. Phone code (sent to your Telegram)
2. 2FA password (if enabled)

Session saved to `gram_session.session` — login only needed once.

### 5. Deploy to VPS (24/7)

```bash
# Copy to VPS
scp -r gram-auto-miner/ ubuntu@YOUR_VPS_IP:/opt/gram-miner/

# SSH to VPS
ssh ubuntu@YOUR_VPS_IP
cd /opt/gram-miner

# Setup
bash setup.sh

# Login first
python3 miner.py

# Start service
systemctl start gram-miner
systemctl status gram-miner
```

## Cloudflare Worker (Optional)

If your VPS gets HTTP 403 from Gram Network API (common on AWS/GCP/Azure), deploy a Cloudflare Worker proxy:

### Quick Deploy

```bash
python3 deploy_worker.py
```

The script will:
1. Ask for Cloudflare Account ID and API Token
2. Deploy the worker automatically
3. Update your config.json with the worker URL

### Manual Deploy

1. Create Cloudflare account (free): https://dash.cloudflare.com
2. Go to **Workers & Pages** > **Create Worker**
3. Paste the worker code from `deploy_worker.py`
4. Deploy and copy the URL
5. Add to config.json: `"worker_url": "https://your-worker.workers.dev"`

### Why Worker?

Cloud IPs (AWS, GCP, Azure) are often blocked by Gram Network API. Cloudflare Worker acts as proxy — requests go through Cloudflare's network, bypassing IP restrictions.

## Architecture

```
┌─────────────┐    RequestWebView     ┌──────────────┐
│  Telethon   │ ──────────────────►  │   Telegram   │
│  Userbot    │ ◄──────────────────  │   Server     │
│             │   Fresh initData     └──────────────┘
└──────┬──────┘
       │
       ▼
┌─────────────────┐     ┌──────────────────┐
│  Cloudflare     │ ──► │  Gram Network    │
│  Worker         │     │  API             │
│  (optional)     │     │                  │
└─────────────────┘     └──────────────────┘
       │
       ▼ (wait 4h)
       │
   💰 Claim → Repeat
```

## Monitoring

```bash
# View logs
tail -f /opt/gram-miner/miner.log

# Check service status
systemctl status gram-miner

# Restart
systemctl restart gram-miner

# Stop
systemctl stop gram-miner
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `config.json not found` | Copy from example: `cp config.example.json config.json` |
| `api_id/api_hash wrong` | Check https://my.telegram.org/apps |
| `HTTP 403` | Deploy Cloudflare Worker (see above) |
| `Unauthorized` | Session expired — run `python3 miner.py` to re-login |
| Bot username error | Check correct username in Telegram |
| Service won't start | Run `python3 miner.py` first to login |

## File Structure

```
gram-auto-miner/
├── miner.py              # Main bot
├── config.example.json   # Config template
├── deploy_worker.py      # Cloudflare Worker deployer
├── setup.sh              # VPS setup script
├── .gitignore            # Excludes config.json, sessions, logs
└── README.md             # This file
```

## License

MIT
