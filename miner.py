#!/usr/bin/env python3
"""
Gram Network Auto Miner - Multi Account
=========================================
Auto mining bot for Gram Network Telegram Mini App.
Supports multiple accounts with random delays and live dashboard.

Setup:
  1. pip3 install telethon requests
  2. Get API credentials: https://my.telegram.org/apps
  3. Copy config.example.json -> config.json, fill your credentials
  4. python3 miner.py  (first run asks for phone codes)
"""

import requests
import json
import time
import sys
import os
import random
import logging
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
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


# ═══════════════════════════════════════════════════════════════════
# ACCOUNT STATE
# ═══════════════════════════════════════════════════════════════════

class AccountState:
    """Tracks state for a single account."""
    def __init__(self, config, index):
        self.index = index
        self.name = config.get("name", f"Account {index + 1}")
        self.api_id = config["api_id"]
        self.api_hash = config["api_hash"]
        self.phone = config["phone"]
        self.password = config.get("password", "")
        self.proxy = config.get("proxy", "")
        
        self.username = None
        self.balance = 0.0
        self.usd_balance = 0.0
        self.mining_status = "unknown"
        self.mining_rate = 0.0
        self.tokens_earned = 0.0
        self.energy = 0
        self.time_left = 0
        self.next_action = None  # datetime of next action
        self.next_action_type = ""  # "claim", "start", "waiting"
        self.error = None
        self.client = None
        self.logged_in = False


# ═══════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════

def load_config():
    if not CONFIG_FILE.exists():
        log.error("config.json not found! Copy config.example.json -> config.json")
        sys.exit(1)
    with open(CONFIG_FILE) as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════
# API CALLS
# ═══════════════════════════════════════════════════════════════════

def api_call(method, endpoint, init_data, worker_url="", proxy=""):
    """Make API call to Gram Network (direct or via Cloudflare Worker)."""
    headers_req = {"User-Agent": "GramMiner/1.0", "Accept": "application/json"}
    proxies = {"http": proxy, "https": proxy} if proxy else None
    
    if worker_url:
        ep = endpoint.replace(".php", "")
        try:
            r = requests.get(
                worker_url,
                params={"endpoint": ep, "initData": init_data},
                headers=headers_req,
                proxies=proxies,
                timeout=30,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.error(f"[API] {method} {endpoint} via worker -> {e}")
            return None
    
    url = f"{BASE_URL}/{endpoint}"
    try:
        if method == "GET":
            r = requests.get(url, params={"initData": init_data}, headers=HEADERS,
                           proxies=proxies, timeout=30)
        else:
            post_h = {**HEADERS, "Content-Type": "application/x-www-form-urlencoded"}
            r = requests.post(url, headers=post_h,
                            data=f"initData={quote(init_data, safe='')}",
                            proxies=proxies, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.error(f"[API] {method} {endpoint} -> {e}")
        return None


# ═══════════════════════════════════════════════════════════════════
# TELETHON - INIT DATA
# ═══════════════════════════════════════════════════════════════════

async def get_fresh_initdata(client, bot_username):
    """Get fresh initData via Telethon."""
    from telethon.tl.functions.messages import RequestAppWebViewRequest, RequestWebViewRequest
    from telethon.tl.functions.contacts import ResolveUsernameRequest
    from telethon.tl.types import InputBotAppShortName, InputUser

    try:
        result = await client(ResolveUsernameRequest(bot_username))
        users = result.users
        if not users:
            return None

        bot_user = users[0]
        bot_input = await client.get_input_entity(bot_user.id)
        peer = await client.get_input_entity(bot_user.id)

        url = None
        for sn in ["app", "game", "miniapp", "start", "webapp", ""]:
            try:
                app = InputBotAppShortName(
                    bot_id=InputUser(user_id=bot_user.id, access_hash=bot_user.access_hash),
                    short_name=sn
                )
                r = await client(RequestAppWebViewRequest(peer=peer, app=app, platform="android",
                                                          url="https://app.gramnetwork.online/"))
                url = r.url
                break
            except:
                continue

        if not url:
            r = await client(RequestWebViewRequest(peer=peer, bot=bot_input, platform="android",
                                                   from_bot_menu=False,
                                                   url="https://app.gramnetwork.online/"))
            url = r.url

        if "tgWebAppData=" in url:
            raw = url.split("tgWebAppData=")[1]
            if "&tgWebAppVersion=" in raw:
                raw = raw.split("&tgWebAppVersion=")[0]
            return unquote(raw)
    except Exception as e:
        log.error(f"[INITDATA] {e}")
    return None


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def fmt_time(seconds):
    if seconds <= 0:
        return "00:00:00"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def fmt_countdown(target):
    """Countdown to a future datetime."""
    if not target:
        return "--:--:--"
    diff = (target - datetime.now()).total_seconds()
    if diff <= 0:
        return "NOW"
    return fmt_time(diff)


def random_delay(max_minutes):
    """Random delay in seconds, 1 to max_minutes."""
    return random.randint(60, max_minutes * 60)


# ═══════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════

def print_dashboard(accounts, cfg):
    """Print multi-account dashboard."""
    os.system('cls' if os.name == 'nt' else 'clear')
    
    total_balance = sum(a.balance for a in accounts)
    active_count = sum(1 for a in accounts if a.mining_status.lower() in ("active", "mining"))
    ready_count = sum(1 for a in accounts if "ready" in a.mining_status.lower() or "claim" in a.mining_status.lower())
    
    print()
    print("=" * 62)
    print("  GRAM NETWORK AUTO MINER - DASHBOARD")
    print("=" * 62)
    print(f"  Accounts: {len(accounts)} | Mining: {active_count} | Ready: {ready_count}")
    print(f"  Total Balance: {total_balance:.2f} GRM")
    if cfg.get("worker_url"):
        print(f"  Worker: {cfg['worker_url'][:40]}...")
    print("=" * 62)
    print()
    print(f"  {'#':<3} {'Name':<15} {'Username':<16} {'Balance':>8} {'Status':<12} {'Next Action':<14} {'Countdown'}")
    print(f"  {'─'*3} {'─'*15} {'─'*16} {'─'*8} {'─'*12} {'─'*14} {'─'*12}")
    
    for i, a in enumerate(accounts):
        name = a.name[:14]
        uname = f"@{a.username}" if a.username else "..."
        bal = f"{a.balance:.2f}"
        status = a.mining_status[:11] if a.mining_status else "unknown"
        
        # Status icon
        if "ready" in status.lower() or "claim" in status.lower():
            icon = "💰"
        elif status.lower().startswith("active") or "mining" in status.lower():
            icon = "⛏️"
        elif a.error:
            icon = "❌"
        else:
            icon = "💤"
        
        next_act = a.next_action_type if a.next_action_type else "-"
        countdown = fmt_countdown(a.next_action)
        
        print(f"  {i+1:<3} {name:<15} {uname:<16} {bal:>8} {icon} {status:<10} {next_act:<14} {countdown}")
    
    print()
    print("=" * 62)
    print(f"  Next refresh in 60s | Ctrl+C to stop")
    print("=" * 62)
    print()


# ═══════════════════════════════════════════════════════════════════
# LOGIN
# ═══════════════════════════════════════════════════════════════════

async def login_account(acc, bot_username):
    """Login a single account via Telethon."""
    from telethon import TelegramClient
    
    session_file = SCRIPT_DIR / f"session_{acc.index}"
    proxy = acc.proxy if acc.proxy else None
    
    # Parse proxy for Telethon format
    telethon_proxy = None
    if proxy:
        from telethon import connection
        if proxy.startswith("socks5"):
            telethon_proxy = (proxy, 1080, "socks5")
        # HTTP proxy not directly supported by Telethon, skip
    
    acc.client = TelegramClient(str(session_file), acc.api_id, acc.api_hash)
    await acc.client.connect()
    
    if not await acc.client.is_user_authorized():
        log.info(f"[{acc.name}] Sending code to {acc.phone}...")
        await acc.client.send_code_request(acc.phone)
        code = input(f"[{acc.name}] Enter code: ")
        try:
            await acc.client.sign_in(acc.phone, code)
        except Exception as e:
            if "password" in str(e).lower():
                if acc.password:
                    await acc.client.sign_in(password=acc.password)
                else:
                    pw = input(f"[{acc.name}] 2FA Password: ")
                    await acc.client.sign_in(password=pw)
            else:
                raise
    
    me = await acc.client.get_me()
    acc.username = me.username
    acc.logged_in = True
    log.info(f"[{acc.name}] Logged in as @{me.username}")


# ═══════════════════════════════════════════════════════════════════
# MINING CYCLE (per account)
# ═══════════════════════════════════════════════════════════════════

async def mining_cycle(acc, cfg):
    """Run mining cycle for a single account."""
    bot_username = cfg.get("bot_username", "gramnetwork_bot")
    worker_url = cfg.get("worker_url", "").rstrip("/")
    max_delay = cfg.get("random_delay_max_minutes", 5)
    
    while True:
        try:
            acc.error = None
            
            # Get fresh initData
            init_data = await get_fresh_initdata(acc.client, bot_username)
            if not init_data:
                acc.error = "initData failed"
                acc.next_action_type = "retry"
                acc.next_action = datetime.now() + timedelta(minutes=5)
                await asyncio.sleep(300)
                continue
            
            # Get user data
            data = api_call("GET", "get_user_data.php", init_data, worker_url, acc.proxy)
            if not data or not data.get("success"):
                acc.error = "API error"
                acc.next_action_type = "retry"
                acc.next_action = datetime.now() + timedelta(minutes=5)
                await asyncio.sleep(300)
                continue
            
            user = data["user"]
            acc.balance = float(user.get("total_balance", 0))
            acc.usd_balance = float(user.get("usd_balance", 0))
            acc.mining_status = user.get("mining_status", "unknown")
            acc.mining_rate = float(user.get("mining_rate", 0))
            acc.tokens_earned = float(user.get("tokens_earned", 0))
            acc.energy = user.get("energy", 0)
            
            # Parse time_left
            raw_tl = user.get("time_left", 0)
            if isinstance(raw_tl, str) and ":" in raw_tl:
                parts = raw_tl.split(":")
                acc.time_left = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            else:
                acc.time_left = int(raw_tl) if raw_tl else 0
            
            # Claim daily
            api_call("POST", "claim_daily.php", init_data, worker_url, acc.proxy)
            
            status = acc.mining_status.lower()
            log.info(f"[{acc.name}] Status='{status}', time_left={acc.time_left}, balance={acc.balance}, earned={acc.tokens_earned}")
            
            # Random delay
            delay = random_delay(max_delay)
            delay_mins = delay // 60
            
            # Ready to claim
            if "ready" in status or "claim" in status:
                log.info(f"[{acc.name}] Pending reward found. Waiting {delay_mins}min before claim...")
                acc.next_action_type = "claim"
                acc.next_action = datetime.now() + timedelta(seconds=delay)
                await asyncio.sleep(delay)
                
                # Re-init data after delay
                init_data = await get_fresh_initdata(acc.client, bot_username)
                if not init_data:
                    continue
                
                claim = api_call("POST", "claim_mining.php", init_data, worker_url, acc.proxy)
                if claim and claim.get("success"):
                    log.info(f"[{acc.name}] Claimed!")
                else:
                    log.info(f"[{acc.name}] Claim result: {claim}")
                
                # Random delay before start
                delay2 = random_delay(max_delay)
                delay2_mins = delay2 // 60
                log.info(f"[{acc.name}] Waiting {delay2_mins}min before starting new session...")
                acc.next_action_type = "start"
                acc.next_action = datetime.now() + timedelta(seconds=delay2)
                await asyncio.sleep(delay2)
                
                init_data = await get_fresh_initdata(acc.client, bot_username)
                if not init_data:
                    continue
                
                result = api_call("POST", "start_mining.php", init_data, worker_url, acc.proxy)
                if result and result.get("success"):
                    log.info(f"[{acc.name}] Mining started!")
                else:
                    log.info(f"[{acc.name}] Start result: {result}")
                
                acc.next_action_type = "claim"
                acc.next_action = datetime.now() + timedelta(seconds=SESSION_SECONDS)
                await asyncio.sleep(SESSION_SECONDS)
            
            # Active mining (only if actually earned something)
            elif ("active" in status or acc.time_left > 0) and acc.tokens_earned > 0:
                wait = acc.time_left + random_delay(max_delay)
                log.info(f"[{acc.name}] Mining active. Next claim in {fmt_time(wait)}")
                acc.next_action_type = "claim"
                acc.next_action = datetime.now() + timedelta(seconds=wait)
                await asyncio.sleep(wait)
                
                init_data = await get_fresh_initdata(acc.client, bot_username)
                if init_data:
                    claim = api_call("POST", "claim_mining.php", init_data, worker_url, acc.proxy)
                    if claim and claim.get("success"):
                        log.info(f"[{acc.name}] Claimed!")
                    else:
                        log.info(f"[{acc.name}] Claim result: {claim}")
                
                # Start new session after claim
                delay2 = random_delay(max_delay)
                log.info(f"[{acc.name}] Waiting {delay2//60}min before starting new session...")
                acc.next_action_type = "start"
                acc.next_action = datetime.now() + timedelta(seconds=delay2)
                await asyncio.sleep(delay2)
                
                init_data = await get_fresh_initdata(acc.client, bot_username)
                if init_data:
                    result = api_call("POST", "start_mining.php", init_data, worker_url, acc.proxy)
                    if result and result.get("success"):
                        log.info(f"[{acc.name}] Mining started!")
                    else:
                        log.info(f"[{acc.name}] Start result: {result}")
                
                acc.next_action_type = "claim"
                acc.next_action = datetime.now() + timedelta(seconds=SESSION_SECONDS)
                await asyncio.sleep(SESSION_SECONDS)
            
            # New account or inactive (balance=0, earned=0, or inactive status)
            else:
                if "active" in status:
                    log.info(f"[{acc.name}] Status says active but balance=0. Starting fresh...")
                else:
                    log.info(f"[{acc.name}] Inactive. Starting in {delay_mins}min...")
                acc.next_action_type = "start"
                acc.next_action = datetime.now() + timedelta(seconds=delay)
                await asyncio.sleep(delay)
                
                init_data = await get_fresh_initdata(acc.client, bot_username)
                if not init_data:
                    continue
                
                result = api_call("POST", "start_mining.php", init_data, worker_url, acc.proxy)
                if result and result.get("success"):
                    log.info(f"[{acc.name}] Mining started!")
                else:
                    log.info(f"[{acc.name}] Start result: {result}")
                
                acc.next_action_type = "claim"
                acc.next_action = datetime.now() + timedelta(seconds=SESSION_SECONDS)
                await asyncio.sleep(SESSION_SECONDS)
        
        except Exception as e:
            acc.error = str(e)[:30]
            log.error(f"[{acc.name}] Cycle error: {e}")
            acc.next_action_type = "retry"
            acc.next_action = datetime.now() + timedelta(minutes=5)
            await asyncio.sleep(300)


# ═══════════════════════════════════════════════════════════════════
# DASHBOARD REFRESH TASK
# ═══════════════════════════════════════════════════════════════════

async def dashboard_task(accounts, cfg):
    """Refresh dashboard every 60 seconds, wait for first data."""
    await asyncio.sleep(10)  # Wait for first mining cycle to fetch data
    while True:
        print_dashboard(accounts, cfg)
        await asyncio.sleep(60)


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

async def main():
    cfg = load_config()
    accounts_cfg = cfg.get("accounts", [])
    
    if not accounts_cfg:
        log.error("No accounts in config.json!")
        sys.exit(1)
    
    if cfg.get("worker_url"):
        log.info(f"Worker: {cfg['worker_url']}")
    
    # Login all accounts
    accounts = []
    for i, acc_cfg in enumerate(accounts_cfg):
        acc = AccountState(acc_cfg, i)
        try:
            await login_account(acc, cfg.get("bot_username", "gramnetwork_bot"))
            accounts.append(acc)
        except Exception as e:
            log.error(f"[{acc.name}] Login failed: {e}")
            acc.error = str(e)[:30]
            accounts.append(acc)
    
    if not accounts:
        log.error("No accounts logged in!")
        sys.exit(1)
    
    log.info(f"Starting mining for {len(accounts)} accounts...")
    
    # Launch: 1 mining task per account + 1 dashboard task
    tasks = [asyncio.create_task(mining_cycle(a, cfg)) for a in accounts if a.logged_in]
    tasks.append(asyncio.create_task(dashboard_task(accounts, cfg)))
    
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped")
