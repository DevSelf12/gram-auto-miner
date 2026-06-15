#!/usr/bin/env python3
"""
Gram Network Auto Miner
========================
Auto mining bot for Gram Network Telegram Mini App.
Uses Telethon to generate fresh initData, then calls Gram API.

Setup:
  1. pip3 install telethon requests
  2. Get API credentials: https://my.telegram.org/apps
  3. Copy config.example.json → config.json, fill your credentials
  4. python3 miner.py  (first run asks for phone code)
"""

import requests
import json
import time
import sys
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from telethon import TelegramClient, functions, types
from urllib.parse import quote, unquote

# ── Paths ───────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "config.json"
LOG_FILE = SCRIPT_DIR / "miner.log"

# ── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("gram-miner")

# ── Gram Network API ────────────────────────────────────────────────
BASE_URL = "https://app.gramnetwork.online/api"
SESSION_SECONDS = 4 * 3600  # 4 hours

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    "Accept": "application/json",
    "Origin": "https://app.gramnetwork.online",
    "Referer": "https://app.gramnetwork.online/",
}


def load_config():
    if not CONFIG_FILE.exists():
        log.error("config.json not found! Copy config.example.json → config.json and fill your credentials.")
        sys.exit(1)
    with open(CONFIG_FILE) as f:
        return json.load(f)


async def get_fresh_initdata(client, bot_username="gramnetwork_bot"):
    """Get fresh initData by requesting WebApp view from Telegram."""
    try:
        from telethon.tl.functions.messages import RequestAppWebViewRequest, RequestWebViewRequest
        from telethon.tl.functions.contacts import ResolveUsernameRequest
        from telethon.tl.types import InputBotAppShortName, InputUser

        result = await client(ResolveUsernameRequest(bot_username))
        users = result.users
        if not users:
            log.error(f"Could not resolve bot @{bot_username}")
            return None

        bot_user = users[0]
        bot_input = await client.get_input_entity(bot_user.id)
        peer = await client.get_input_entity(bot_user.id)

        log.info(f"Resolved @{bot_username} -> user_id={bot_user.id}")

        # Try RequestAppWebViewRequest with different short names
        url = None
        short_names = ["app", "game", "miniapp", "start", "webapp", ""]
        
        for short_name in short_names:
            try:
                app = InputBotAppShortName(
                    bot_id=InputUser(
                        user_id=bot_user.id,
                        access_hash=bot_user.access_hash
                    ),
                    short_name=short_name
                )
                r = await client(RequestAppWebViewRequest(
                    peer=peer,
                    app=app,
                    platform="android",
                    url="https://app.gramnetwork.online/",
                ))
                url = r.url
                log.info(f"RequestAppWebViewRequest success (short_name='{short_name}')")
                break
            except Exception as e:
                log.debug(f"short_name='{short_name}' failed: {e}")
                continue

        # Fallback to RequestWebViewRequest
        if not url:
            log.info("Falling back to RequestWebViewRequest...")
            r = await client(RequestWebViewRequest(
                peer=peer,
                bot=bot_input,
                platform="android",
                from_bot_menu=False,
                url="https://app.gramnetwork.online/",
            ))
            url = r.url
        log.info(f"WebView URL (full): {url}")

        if "tgWebAppData=" in url:
            raw = url.split("tgWebAppData=")[1]
            if "&tgWebAppVersion=" in raw:
                raw = raw.split("&tgWebAppVersion=")[0]
            init_data = unquote(raw)
            log.info("Got fresh initData from Telegram!")
            log.info(f"initData length: {len(init_data)}")
            log.info(f"Has hash: {'hash=' in init_data}")
            log.info(f"Has signature: {'signature=' in init_data}")
            return init_data
        else:
            log.error(f"Could not extract initData from URL: {url[:100]}")
            return None

    except Exception as e:
        log.error(f"Failed to get initData: {type(e).__name__}: {e}")
        return None


def api_call(method, endpoint, init_data):
    """Make API call to Gram Network (direct or via Cloudflare Worker)."""
    global cfg
    worker_url = cfg.get("worker_url", "").rstrip("/")
    
    if worker_url:
        # Route through Cloudflare Worker
        ep = endpoint.replace(".php", "")
        try:
            r = requests.get(worker_url, params={"endpoint": ep, "initData": init_data}, 
                            headers={"User-Agent": "GramMiner/1.0", "Accept": "application/json"}, 
                            timeout=30)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError:
            log.error(f"{method} {endpoint} -> HTTP {r.status_code}: {r.text[:200]}")
            return None
        except Exception as e:
            log.error(f"{method} {endpoint} -> {e}")
            return None
    
    # Direct API call
    url = f"{BASE_URL}/{endpoint}"
    try:
        if method == "GET":
            r = requests.get(url, params={"initData": init_data}, headers=HEADERS, timeout=30)
        else:
            post_headers = {**HEADERS, "Content-Type": "application/x-www-form-urlencoded"}
            r = requests.post(url, headers=post_headers, 
                            data=f"initData={quote(init_data, safe='')}", 
                            timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError:
        log.error(f"{method} {endpoint} -> HTTP {r.status_code}: {r.text[:200]}")
        return None
    except Exception as e:
        log.error(f"{method} {endpoint} -> {e}")
        return None


def fmt_time(seconds):
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def print_status(user):
    if not user:
        return
    log.info("=" * 50)
    log.info(f"User: {user.get('first_name', 'N/A')} (@{user.get('username', 'N/A')})")
    log.info(f"Balance: {user.get('total_balance', 0)} GRM (${user.get('usd_balance', 0)})")
    log.info(f"Mining: {user.get('mining_status', 'N/A')}")
    log.info(f"Rate: {user.get('mining_rate', 0)} GRM/hr | Power: {user.get('mining_power', 0)} GH/s")
    log.info(f"Earned: {user.get('tokens_earned', 0)} GRM")
    log.info(f"Energy: {user.get('energy', 'N/A')}")
    time_left = user.get('time_left', 0)
    if isinstance(time_left, str):
        log.info(f"Time Left: {time_left}")
    else:
        log.info(f"Time Left: {fmt_time(time_left)}")
    log.info("=" * 50)


async def main():
    global cfg
    cfg = load_config()
    if cfg.get("worker_url"):
        log.info(f"Using Cloudflare Worker: {cfg['worker_url']}")
    else:
        log.info("Direct API mode (no worker)")

    # ── Init Telethon ───────────────────────────────────────────────
    api_id = cfg["api_id"]
    api_hash = cfg["api_hash"]
    phone = cfg["phone"]
    bot_username = cfg.get("bot_username", "gramnetwork_bot")

    session_file = SCRIPT_DIR / "gram_session"
    password = cfg.get("password", None)
    client = TelegramClient(str(session_file), api_id, api_hash)

    # Login with proper 2FA handling
    await client.connect()
    if not await client.is_user_authorized():
        log.info(f"Sending code to {phone}...")
        await client.send_code_request(phone)
        code = input("Enter the code you received: ")
        try:
            await client.sign_in(phone, code)
        except Exception as e:
            if "password" in str(e).lower() or "TwoStepVerificationError" in type(e).__name__:
                if password:
                    log.info("Using 2FA password from config...")
                    await client.sign_in(password=password)
                else:
                    log.info("2FA required. Enter your Telegram cloud password:")
                    pw = input("Password: ")
                    await client.sign_in(password=pw)
                    log.info("Tip: add \"password\" to config.json so you don't need to type it again.")
            else:
                raise

    me = await client.get_me()
    log.info(f"Logged in as {me.first_name} (@{me.username})")

    # ── Main loop ───────────────────────────────────────────────────
    while True:
        # Get fresh initData each cycle
        log.info("Getting fresh initData...")
        init_data = await get_fresh_initdata(client, bot_username)

        if not init_data:
            log.error("Failed to get initData. Retrying in 5 minutes...")
            await asyncio.sleep(300)
            continue

        # Get user data
        data = api_call("GET", "get_user_data.php", init_data)
        if not data or not data.get("success"):
            log.error(f"API error: {data}")
            await asyncio.sleep(300)
            continue

        user = data["user"]
        print_status(user)

        # Claim daily reward
        daily = api_call("POST", "claim_daily.php", init_data)
        if daily and daily.get("success"):
            log.info("Daily reward claimed!")

        mining_status = user.get("mining_status", "").lower()
        log.info(f"Mining status: '{mining_status}'")

        # Parse time_left (can be int seconds or string "HH:MM:SS")
        raw_time_left = user.get("time_left", 0)
        if isinstance(raw_time_left, str) and ":" in raw_time_left:
            parts = raw_time_left.split(":")
            time_left = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        else:
            time_left = int(raw_time_left) if raw_time_left else 0

        # Priority: claim pending reward first
        if "ready" in mining_status or "claim" in mining_status:
            log.info("Found pending reward! Claiming now...")
            claim = api_call("POST", "claim_mining.php", init_data)
            if claim and claim.get("success"):
                log.info(f"Claimed! {claim}")
            else:
                log.info(f"Claim result: {claim}")

            # Start new session after claim
            log.info("Starting new mining session...")
            result = api_call("POST", "start_mining.php", init_data)
            if result and result.get("success"):
                log.info("Mining started! Session: 4h")
            else:
                log.info(f"Start result: {result}")

            log.info("Sleeping 4 hours...")
            await asyncio.sleep(SESSION_SECONDS)

        elif mining_status == "active" or (time_left > 0 and "ready" not in mining_status):
            # Wait for current session to finish
            log.info(f"Mining active. Waiting {fmt_time(time_left)}...")
            await asyncio.sleep(min(time_left + 30, SESSION_SECONDS))

            # Claim
            log.info("Claiming tokens...")
            claim = api_call("POST", "claim_mining.php", init_data)
            if claim and claim.get("success"):
                log.info(f"Claimed! {claim}")
            else:
                log.info(f"Claim result: {claim}")
        else:
            # Start new session
            log.info("Starting mining...")
            result = api_call("POST", "start_mining.php", init_data)
            if result and result.get("success"):
                log.info("Mining started! Session: 4h")
            else:
                log.info(f"Start result: {result}")

            log.info("Sleeping 4 hours...")
            await asyncio.sleep(SESSION_SECONDS)

            # Get fresh initData for claim
            init_data = await get_fresh_initdata(client, bot_username)
            if init_data:
                claim = api_call("POST", "claim_mining.php", init_data)
                if claim and claim.get("success"):
                    log.info(f"Claimed after session! {claim}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped")
